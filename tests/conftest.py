"""Shared pytest fixtures. (No path setup needed — gmail-cleanup is installed via pip install -e .)"""

import os
import tempfile

import pytest

# gmail_cleanup builds its list constants at import time from ~/.gmail_cli/lists.
# Swap HOME before any test module imports it, so the session never sees the
# developer's real lists (tests passed locally but failed in CI because of this).
os.environ['HOME'] = tempfile.mkdtemp(prefix='gmail-cleanup-test-home-')


@pytest.fixture(autouse=True)
def _isolate_home(monkeypatch, tmp_path_factory):
    """Point HOME at a throwaway directory so no test can touch the real ~/.gmail_cli."""
    monkeypatch.setenv('HOME', str(tmp_path_factory.mktemp('home')))
