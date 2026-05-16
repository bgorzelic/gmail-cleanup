"""Tests for the credentials.json search-path logic.

The lookup order is intentional and user-visible (the error message lists every
checked path), so changes to it should be reflected here.
"""

import os
from pathlib import Path

import pytest

import gmail_cleanup as gmail_cli


@pytest.fixture
def isolated_env(monkeypatch, tmp_path):
    """Run each test with HOME and CWD pointing at a clean tmp dir."""
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('GMAIL_CLEANUP_CREDENTIALS', raising=False)
    # CREDS_DIR is computed at module import — patch it to follow HOME.
    monkeypatch.setattr(gmail_cli, 'CREDS_DIR', Path(os.environ['HOME']) / '.gmail_cli')
    return tmp_path


class TestSearchPaths:
    def test_default_paths_in_order(self, isolated_env):
        paths = gmail_cli._credentials_search_paths()
        # Order: env-var > ~/.gmail_cli > cwd > package dir
        assert paths[0] == Path(os.environ['HOME']) / '.gmail_cli' / 'credentials.json'
        assert paths[1] == Path.cwd() / 'credentials.json'
        # Last entry should be the package-relative path (this one moves with the codebase).
        assert paths[-1].name == 'credentials.json'

    def test_env_var_takes_precedence(self, isolated_env, monkeypatch):
        custom = isolated_env / 'somewhere' / 'creds.json'
        monkeypatch.setenv('GMAIL_CLEANUP_CREDENTIALS', str(custom))
        paths = gmail_cli._credentials_search_paths()
        assert paths[0] == custom

    def test_env_var_expands_tilde(self, isolated_env, monkeypatch):
        monkeypatch.setenv('GMAIL_CLEANUP_CREDENTIALS', '~/my-creds.json')
        paths = gmail_cli._credentials_search_paths()
        assert paths[0] == Path(os.environ['HOME']) / 'my-creds.json'


class TestFindCredentialsFile:
    """End-to-end resolution tests.

    The package-dir fallback (last entry in the search order) can't be cleanly
    isolated in a unit test — it's tied to where the module file lives — so
    these tests verify that *earlier* entries are respected, which is the
    interesting behavior. The package-dir fallback is exercised by the
    integration test in the README/CHANGELOG (running from a fresh /tmp with
    no creds anywhere).
    """

    def test_finds_in_cwd(self, isolated_env):
        cwd_creds = isolated_env / 'credentials.json'
        cwd_creds.write_text('{}')
        found = gmail_cli._find_credentials_file()
        assert found == cwd_creds

    def test_canonical_location_beats_cwd(self, isolated_env):
        """When both ~/.gmail_cli/credentials.json and ./credentials.json exist,
        the canonical per-user location wins (it's earlier in the search order)."""
        home_creds_dir = isolated_env / 'home' / '.gmail_cli'
        home_creds_dir.mkdir(parents=True)
        home_creds = home_creds_dir / 'credentials.json'
        home_creds.write_text('{}')
        cwd_creds = isolated_env / 'credentials.json'
        cwd_creds.write_text('{}')
        found = gmail_cli._find_credentials_file()
        assert found == home_creds

    def test_env_var_beats_canonical_location(self, isolated_env, monkeypatch):
        custom = isolated_env / 'explicit-creds.json'
        custom.write_text('{}')
        monkeypatch.setenv('GMAIL_CLEANUP_CREDENTIALS', str(custom))
        # Also stage a canonical-location file — env var should still win.
        home_creds_dir = isolated_env / 'home' / '.gmail_cli'
        home_creds_dir.mkdir(parents=True)
        (home_creds_dir / 'credentials.json').write_text('{}')
        assert gmail_cli._find_credentials_file() == custom
