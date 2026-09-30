"""Review findings for gmail_cleanup/state.py and gmail_cleanup/lists_io.py.

Each test here reproduces a bug that was proven against the pre-fix code; see
docs/review-state-lists.md for the reproductions and severity.
"""

import json
import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

import gmail_cleanup as gmail_cli
from gmail_cleanup import state
from gmail_cleanup.lists_io import _normalize_unsubbed_entry, append_to_unsubbed
from gmail_cleanup.state import append_event, read_state


@pytest.fixture
def isolated_home(monkeypatch, tmp_path):
    home = tmp_path / 'home'
    (home / '.gmail_cli').mkdir(parents=True)
    monkeypatch.setenv('HOME', str(home))
    return home / '.gmail_cli'


@pytest.fixture
def isolated_lists(monkeypatch, tmp_path, request):
    lists_dir = tmp_path / 'lists'
    lists_dir.mkdir()
    monkeypatch.setattr(gmail_cli, 'LISTS_DIR', lists_dir)
    monkeypatch.setattr(gmail_cli, 'user_lists_dir', lambda: lists_dir)

    def still_isolated():
        if Path(gmail_cli.LISTS_DIR) != lists_dir:
            raise AssertionError(
                f'LISTS_DIR reverted to {gmail_cli.LISTS_DIR} mid-test; '
                'a later append would have written to the repository copy'
            )

    request.addfinalizer(still_isolated)
    return lists_dir


@contextmanager
def failing_replace():
    """Make the atomic rename fail, restoring only that patch afterwards."""
    def boom(self, target):
        raise OSError('simulated failure')

    with patch.object(Path, 'replace', boom):
        yield


def _senders(text):
    """Sender strings from a written unsubbed.yaml, old or mapping format."""
    return [_normalize_unsubbed_entry(e) for e in yaml.safe_load(text)]


def _tmp_files(directory):
    return sorted(p.name for p in directory.glob('*.tmp'))


def _run_concurrently(workers):
    """Run `workers` at the same time; return their results or None if stuck."""
    barrier = threading.Barrier(len(workers))
    results = [None] * len(workers)

    def run(i, fn):
        barrier.wait()
        try:
            results[i] = fn(i)
        except Exception as exc:  # noqa: BLE001
            results[i] = f'{type(exc).__name__}: {exc}'

    threads = [threading.Thread(target=run, args=(i, fn)) for i, fn in enumerate(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    if any(t.is_alive() for t in threads):
        pytest.fail('concurrent workers deadlocked')
    return results


# --------------------------------------------------------------- finding 1
# lists_io.append_to_unsubbed concatenated the preserved header and the dumped
# body without checking the header ended in a newline. On a file whose last
# comment line was unterminated, the first new entry was glued onto that comment
# and vanished: append_to_unsubbed reported it as added, the CLI printed a
# success line, and the sender was gone from the list and from every later
# rewrite of it.
def test_append_to_unsubbed_does_not_swallow_entry_when_header_has_no_newline(isolated_lists):
    path = isolated_lists / 'unsubbed.yaml'
    path.write_text('# Auto-managed by gmail-cleanup. Manual edits preserved.')

    assert append_to_unsubbed(['victim@example.com']) == ['victim@example.com']
    assert _senders(path.read_text()) == ['victim@example.com']


def test_appended_entry_survives_a_later_append(isolated_lists):
    path = isolated_lists / 'unsubbed.yaml'
    path.write_text('# header without a trailing newline')

    append_to_unsubbed(['first@example.com'])
    append_to_unsubbed(['second@example.com'])

    assert _senders(path.read_text()) == ['first@example.com', 'second@example.com']


def test_append_to_unsubbed_keeps_entry_when_file_is_all_comments(isolated_lists):
    path = isolated_lists / 'unsubbed.yaml'
    path.write_text('# emptied by hand\n# second comment line, also unterminated')

    append_to_unsubbed(['kept@example.com'])

    assert _senders(path.read_text()) == ['kept@example.com']


# --------------------------------------------------------------- finding 2
# Both writers derived one fixed temp name from the target, and nothing
# serialised the read-modify-write. A scheduled autopilot running alongside a
# manual command lost events: eight concurrent appends recorded one event, the
# rest raised FileNotFoundError out of the rename, uncaught by every caller.
def test_concurrent_append_event_records_every_event(isolated_home):
    results = _run_concurrently(
        [lambda i: append_event('race@example.com', 'mark-read', {'unread_delta': -1, 'w': i})
         for _ in range(8)]
    )

    assert results == [None] * 8, f'workers raised: {[r for r in results if r]}'
    history = read_state('race@example.com')['history']
    assert len(history) == 8
    assert {e['w'] for e in history} == set(range(8))


def test_concurrent_append_to_unsubbed_records_every_sender(isolated_lists):
    path = isolated_lists / 'unsubbed.yaml'
    path.write_text('# header\n')

    senders = [f'racer{i}@example.com' for i in range(8)]
    _run_concurrently([lambda i: append_to_unsubbed([senders[i]]) for i in range(8)])

    # Order depends on which worker takes the lock, so compare as a set.
    assert set(_senders(path.read_text())) == set(senders)


# --------------------------------------------------------------- finding 3
# A failure between the write and the rename left the temp file behind holding
# the only copy of the newer data, and the next run overwrote it. Both files
# also leaked a stray .tmp into the state and lists directories.
@pytest.mark.parametrize('target', ['state', 'lists'])
def test_failed_write_leaves_no_stray_temp_file(isolated_home, isolated_lists, target):
    if target == 'state':
        path = state._path('crash@example.com')

        def change():
            append_event('crash@example.com', 'autopilot', {'trigger': 'manual'})
    else:
        path = isolated_lists / 'unsubbed.yaml'
        path.write_text('# header\n- old@example.com\n')

        def change():
            append_to_unsubbed(['new@example.com'])

    with failing_replace(), pytest.raises(OSError):
        change()

    assert _tmp_files(path.parent) == []
    if target == 'lists':
        assert _senders(path.read_text()) == ['old@example.com']
    else:
        assert not path.exists()


def test_failed_write_does_not_strand_the_new_version(isolated_lists):
    path = isolated_lists / 'unsubbed.yaml'
    path.write_text('# header\n- old@example.com\n')

    with failing_replace(), pytest.raises(OSError):
        append_to_unsubbed(['new@example.com'])

    # The failed run's version must not survive anywhere to be half-adopted:
    # pre-fix it sat in unsubbed.yaml.tmp until the next run overwrote it.
    assert _tmp_files(isolated_lists) == []
    assert 'new@example.com' not in path.read_text()
    append_to_unsubbed(['later@example.com'])
    assert _senders(path.read_text()) == ['old@example.com', 'later@example.com']


# --------------------------------------------------------------- finding 4
# append_event built the event as {'at': now, 'source': source, **deltas}, so a
# delta could overwrite the timestamp and source of record. status rolls up the
# 7-day window off that 'at', so a clobbered value dropped the event out of the
# dashboard while last_autopilot_at still held the real time.
def test_deltas_cannot_override_event_timestamp_or_source(isolated_home):
    append_event('d@example.com', 'autopilot', {'at': 'not-a-timestamp', 'source': 'spoofed'})

    state_file = read_state('d@example.com')
    event = state_file['history'][0]
    assert event['source'] == 'autopilot'
    assert event['at'] == state_file['last_autopilot_at']


def test_deltas_are_still_recorded(isolated_home):
    append_event('d2@example.com', 'autopilot', {'unread_delta': -10, 'trigger': 'scheduled'})

    event = read_state('d2@example.com')['history'][0]
    assert event['unread_delta'] == -10
    assert event['trigger'] == 'scheduled'


# --------------------------------------------------------------- finding 5
# read_state only guarded against json.JSONDecodeError and returned whatever
# shape the file held. A state file with stray non-UTF-8 bytes raised out of
# `status`, and a file holding a list (or a non-list 'history') made
# append_event raise AttributeError *after* the Gmail work was already done --
# with no caller around append_event to catch it.
def test_read_state_survives_undecodable_bytes(isolated_home):
    state._path('bin@example.com').write_bytes(b'{"history": [], "note": "\xff\xfe"}')

    assert read_state('bin@example.com')['history'] == []


@pytest.mark.parametrize(
    'payload',
    ['[]', 'null', '"text"', '{"history": "not-a-list"}', '{"history": {"a": 1}}', ''],
)
def test_append_event_survives_malformed_state_file(isolated_home, payload):
    state._path('bad@example.com').write_text(payload)

    append_event('bad@example.com', 'autopilot', {'trigger': 'manual'})

    written = json.loads(state._path('bad@example.com').read_text())
    assert len(written['history']) == 1
    assert written['history'][0]['source'] == 'autopilot'


def test_malformed_state_file_does_not_discard_usable_fields(isolated_home):
    state._path('partial@example.com').write_text('{"history": 5, "last_autopilot_at": "T0"}')

    assert read_state('partial@example.com') == {
        'history': [],
        'last_autopilot_at': 'T0',
    }


def test_truncated_state_file_resets_rather_than_crashing(isolated_home):
    """A half-written file is the case a crash mid-rename would leave."""
    state._path('cut@example.com').write_text('{"history": [{"at": "T0", "sou')

    assert read_state('cut@example.com')['history'] == []


# --------------------------------------------------------------- regression
# The pre-existing guarantees these two modules are relied on for.
def test_successful_write_leaves_no_temp_file(isolated_home, isolated_lists):
    append_event('clean@example.com', 'autopilot', {'trigger': 'manual'})
    append_to_unsubbed(['someone@example.com'])

    assert _tmp_files(isolated_home) == []
    assert _tmp_files(isolated_lists) == []


def test_written_list_is_still_a_top_level_list_with_header(isolated_lists):
    path = isolated_lists / 'unsubbed.yaml'
    path.write_text('# header comment\n- foo@example.com\n')

    append_to_unsubbed(['bar@example.com'])

    text = path.read_text()
    assert text.startswith('# header comment\n')
    assert _senders(text) == ['foo@example.com', 'bar@example.com']


def test_history_cap_still_applies_under_lock(isolated_home):
    for i in range(35):
        append_event('cap@example.com', 'unsubscribe', {'new_unsubs': i})

    history = read_state('cap@example.com')['history']
    assert len(history) == 30
    assert [e['new_unsubs'] for e in history] == list(range(5, 35))
