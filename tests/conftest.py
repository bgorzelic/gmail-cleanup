"""Shared pytest fixtures. (No path setup needed — gmail-cleanup is installed via pip install -e .)"""

import pytest


@pytest.fixture(autouse=True)
def _isolate_home(monkeypatch, tmp_path_factory):
    """Point HOME at a throwaway directory so no test can touch the real ~/.gmail_cli."""
    monkeypatch.setenv('HOME', str(tmp_path_factory.mktemp('home')))
