"""Tests for multi-account dispatch pattern."""

from unittest.mock import MagicMock

import pytest

from gmail_cleanup.accounts import add_account, list_accounts
from gmail_cleanup.config import init_config


@pytest.fixture
def isolated_env(monkeypatch, tmp_path):
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    (tmp_path / 'home' / '.gmail_cli').mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('GMAIL_CLEANUP_CONFIG', raising=False)
    init_config()
    return tmp_path


def test_loop_collects_failures(isolated_env):
    add_account('a@example.com')
    add_account('b@example.com')
    func = MagicMock(side_effect=[None, RuntimeError('boom')])
    failures = []
    for acc in list_accounts():
        try:
            func(acc['email'])
        except Exception:
            failures.append(acc['email'])
    assert failures == ['b@example.com']


def test_loop_continues_after_failure(isolated_env):
    add_account('a@example.com')
    add_account('b@example.com')
    calls = []
    def func(email):
        calls.append(email)
        if email == 'a@example.com':
            raise RuntimeError('boom')
    for acc in list_accounts():
        try:
            func(acc['email'])
        except Exception:
            pass
    assert calls == ['a@example.com', 'b@example.com']
