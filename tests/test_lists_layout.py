"""Packaged seed lists vs. per-user lists in ~/.gmail_cli/lists/."""

from datetime import UTC, datetime

import pytest

import gmail_cleanup as gmail_cli
from gmail_cleanup.lists_io import (
    append_to_unsubbed,
    load_unsubbed_entries,
    load_unsubbed_senders,
)


@pytest.fixture
def dirs(monkeypatch, tmp_path):
    seed = tmp_path / 'seed'
    user = tmp_path / 'user'
    seed.mkdir()
    monkeypatch.setattr(gmail_cli, 'LISTS_DIR', seed)
    monkeypatch.setattr(gmail_cli, 'user_lists_dir', lambda: user)
    return seed, user


def test_user_lists_dir_follows_home(monkeypatch, tmp_path):
    monkeypatch.setenv('HOME', str(tmp_path))
    assert gmail_cli.user_lists_dir() == tmp_path / '.gmail_cli' / 'lists'


def test_append_writes_user_file_not_seed(dirs):
    seed, user = dirs
    (seed / 'unsubbed.yaml').write_text('# seed\n- seeded@example.com\n')
    assert append_to_unsubbed(['new@example.com']) == ['new@example.com']
    assert 'new@example.com' not in (seed / 'unsubbed.yaml').read_text()
    assert 'new@example.com' in (user / 'unsubbed.yaml').read_text()


def test_append_dedupes_against_seed(dirs):
    seed, user = dirs
    (seed / 'unsubbed.yaml').write_text('- seeded@example.com\n')
    assert append_to_unsubbed(['seeded@example.com']) == []
    assert not (user / 'unsubbed.yaml').exists()


def test_load_merges_seed_then_user(dirs):
    seed, user = dirs
    user.mkdir()
    (seed / 'unsubbed.yaml').write_text('- a@example.com\n- b@example.com\n')
    (user / 'unsubbed.yaml').write_text('- b@example.com\n- c@example.com\n')
    assert load_unsubbed_senders() == ['a@example.com', 'b@example.com', 'c@example.com']


def test_entries_carry_timestamps(dirs):
    _, user = dirs
    user.mkdir()
    (user / 'unsubbed.yaml').write_text(
        '- old@example.com\n'
        '- sender: new@example.com\n'
        "  unsubscribed_at: '2026-09-01T12:00:00Z'\n"
        '- sender: bad@example.com\n'
        "  unsubscribed_at: 'not a date'\n"
    )
    assert load_unsubbed_entries() == [
        ('old@example.com', None),
        ('new@example.com', datetime(2026, 9, 1, 12, tzinfo=UTC)),
        ('bad@example.com', None),
    ]


def test_latest_timestamp_wins_for_duplicate_sender(dirs):
    seed, user = dirs
    user.mkdir()
    (seed / 'unsubbed.yaml').write_text(
        "- sender: x@example.com\n  unsubscribed_at: '2026-01-01T00:00:00Z'\n"
    )
    (user / 'unsubbed.yaml').write_text(
        "- sender: x@example.com\n  unsubscribed_at: '2026-06-01T00:00:00Z'\n"
    )
    assert load_unsubbed_entries() == [('x@example.com', datetime(2026, 6, 1, tzinfo=UTC))]
