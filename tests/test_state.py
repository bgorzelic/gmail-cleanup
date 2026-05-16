import os
from pathlib import Path

import pytest

from gmail_cleanup.state import append_event, read_state


@pytest.fixture
def isolated_env(monkeypatch, tmp_path):
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    (tmp_path / 'home' / '.gmail_cli').mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_read_empty_returns_default(isolated_env):
    state = read_state('a@example.com')
    assert state['history'] == []
    assert state.get('last_autopilot_at') is None


def test_append_event_persists(isolated_env):
    append_event('a@example.com', source='autopilot', deltas={'unread_delta': -10})
    state = read_state('a@example.com')
    assert len(state['history']) == 1
    assert state['history'][0]['source'] == 'autopilot'


def test_append_event_sets_last_autopilot(isolated_env):
    append_event('a@example.com', source='autopilot', deltas={})
    assert read_state('a@example.com')['last_autopilot_at'] is not None


def test_history_capped_at_30(isolated_env):
    for i in range(35):
        append_event('a@example.com', source='unsubscribe', deltas={'new_unsubs': i})
    assert len(read_state('a@example.com')['history']) == 30


def test_per_account_isolation(isolated_env):
    append_event('a@example.com', source='autopilot', deltas={'unread_delta': -5})
    append_event('b@example.com', source='autopilot', deltas={'unread_delta': -10})
    assert read_state('a@example.com')['history'][0]['unread_delta'] == -5
    assert read_state('b@example.com')['history'][0]['unread_delta'] == -10
