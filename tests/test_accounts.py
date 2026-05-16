import os
from pathlib import Path

import pytest

from gmail_cleanup.accounts import add_account, list_accounts, remove_account
from gmail_cleanup.config import init_config


@pytest.fixture
def isolated_env(monkeypatch, tmp_path):
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    (tmp_path / 'home' / '.gmail_cli').mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('GMAIL_CLEANUP_CONFIG', raising=False)
    init_config()
    return tmp_path


def test_list_empty_initially(isolated_env):
    assert list_accounts() == []


def test_add_account_persists(isolated_env):
    add_account('a@example.com', label='personal')
    accounts = list_accounts()
    assert len(accounts) == 1
    assert accounts[0]['email'] == 'a@example.com'
    assert accounts[0]['label'] == 'personal'


def test_add_duplicate_email_replaces(isolated_env):
    add_account('a@example.com', label='personal')
    add_account('a@example.com', label='work')
    accounts = list_accounts()
    assert len(accounts) == 1
    assert accounts[0]['label'] == 'work'


def test_remove_account(isolated_env):
    add_account('a@example.com', label='personal')
    add_account('b@example.com', label='work')
    assert remove_account('a@example.com') is True
    assert [a['email'] for a in list_accounts()] == ['b@example.com']


def test_remove_unknown_returns_false(isolated_env):
    assert remove_account('no-such@example.com') is False
