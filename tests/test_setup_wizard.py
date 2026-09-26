"""Tests for setup wizard helpers — no real browser, no real stdin, no network."""

import time
from pathlib import Path
from unittest.mock import patch

import gmail_cleanup.setup_wizard as sw


class TestPressEnter:
    def test_calls_input_with_prompt(self, monkeypatch):
        calls = []
        monkeypatch.setattr("builtins.input", lambda p: calls.append(p) or "")
        sw._press_enter("Do the thing")
        assert calls == ["\n  Do the thing\n"]

    def test_default_prompt(self, monkeypatch):
        calls = []
        monkeypatch.setattr("builtins.input", lambda p: calls.append(p) or "")
        sw._press_enter()
        assert calls == ["\n  Press Enter when done...\n"]


class TestOpenBrowser:
    def test_calls_webbrowser_open(self, monkeypatch):
        opened = []
        monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))
        sw._open_browser("https://example.com")
        assert opened == ["https://example.com"]

    def test_prints_url(self, monkeypatch, capsys):
        monkeypatch.setattr("webbrowser.open", lambda url: None)
        sw._open_browser("https://example.com")
        out = capsys.readouterr().out
        assert "https://example.com" in out


class TestFindRecentDownload:
    def test_returns_none_when_downloads_dir_missing(self, tmp_path, monkeypatch):
        missing = tmp_path / "no_such_dir"
        monkeypatch.setattr(sw, "DOWNLOADS", missing)
        assert sw._find_recent_download() is None

    def test_returns_none_when_no_matching_files(self, tmp_path, monkeypatch):
        (tmp_path / "unrelated.txt").write_text("hello")
        monkeypatch.setattr(sw, "DOWNLOADS", tmp_path)
        assert sw._find_recent_download() is None

    def test_finds_recent_client_secret(self, tmp_path, monkeypatch):
        creds = tmp_path / "client_secret_123.json"
        creds.write_text("{}")
        # Ensure mtime is within the window
        monkeypatch.setattr(sw, "DOWNLOADS", tmp_path)
        result = sw._find_recent_download(window_secs=300)
        assert result == creds

    def test_ignores_old_files(self, tmp_path, monkeypatch):
        creds = tmp_path / "client_secret_old.json"
        creds.write_text("{}")
        # Set mtime to 1 hour ago
        old = time.time() - 3600
        creds.touch()
        import os
        os.utime(creds, (old, old))
        monkeypatch.setattr(sw, "DOWNLOADS", tmp_path)
        assert sw._find_recent_download(window_secs=300) is None

    def test_returns_most_recent_when_multiple(self, tmp_path, monkeypatch):
        old = tmp_path / "client_secret_old.json"
        old.write_text("{}")
        import os
        os.utime(old, (time.time() - 600, time.time() - 600))

        recent = tmp_path / "client_secret_recent.json"
        recent.write_text("{}")
        # recent has current mtime (freshly written)

        monkeypatch.setattr(sw, "DOWNLOADS", tmp_path)
        # window large enough to include both
        result = sw._find_recent_download(window_secs=700)
        assert result == recent
