"""Tests for gmail_cleanup/progress.py progress UI wrapper."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from gmail_cleanup import progress as progress_module
from gmail_cleanup.progress import (
    set_mode,
    is_quiet,
    is_verbose,
    vprint,
    progress_for,
    advance,
)


class TestModeSwitching:
    """set_mode and mode queries."""

    def test_set_mode_quiet(self):
        set_mode("quiet")
        assert is_quiet() is True
        assert is_verbose() is False

    def test_set_mode_normal(self):
        set_mode("normal")
        assert is_quiet() is False
        assert is_verbose() is False

    def test_set_mode_verbose(self):
        set_mode("verbose")
        assert is_quiet() is False
        assert is_verbose() is True

    def test_set_mode_invalid_raises(self):
        with pytest.raises(AssertionError):
            set_mode("invalid")


class TestVPrint:
    """vprint only outputs in verbose mode."""

    def test_vprint_suppressed_in_quiet(self, capsys):
        set_mode("quiet")
        vprint("should not appear")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_vprint_suppressed_in_normal(self, capsys):
        set_mode("normal")
        vprint("should not appear")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_vprint_outputs_in_verbose(self, capsys):
        set_mode("verbose")
        vprint("hello verbose")
        captured = capsys.readouterr()
        assert "hello verbose" in captured.out


class TestProgressFor:
    """progress_for context manager behavior."""

    def test_progress_for_returns_none_in_quiet_mode(self):
        set_mode("quiet")
        with progress_for("testing", 10) as handle:
            assert handle is None

    def test_progress_for_returns_none_when_total_zero(self):
        set_mode("normal")
        with progress_for("testing", 0) as handle:
            assert handle is None

    def test_progress_for_returns_progress_and_task_id_in_normal(self):
        set_mode("normal")
        with progress_for("testing", 5) as handle:
            assert handle is not None
            progress_obj, task_id = handle
            assert progress_obj is not None
            assert task_id is not None

    def test_progress_for_returns_progress_and_task_id_in_verbose(self):
        set_mode("verbose")
        with progress_for("testing", 5) as handle:
            assert handle is not None
            progress_obj, task_id = handle
            assert progress_obj is not None
            assert task_id is not None


class TestAdvance:
    """advance function behavior."""

    def test_advance_noop_when_handle_none(self):
        # Should not raise
        advance(None, by=1)
        advance(None, by=5)

    def test_advance_calls_progress_advance(self):
        set_mode("normal")
        mock_progress = MagicMock()
        mock_task_id = MagicMock()
        handle = (mock_progress, mock_task_id)

        advance(handle, by=3)

        mock_progress.advance.assert_called_once_with(mock_task_id, advance=3)

    def test_advance_default_by_one(self):
        set_mode("normal")
        mock_progress = MagicMock()
        mock_task_id = MagicMock()
        handle = (mock_progress, mock_task_id)

        advance(handle)

        mock_progress.advance.assert_called_once_with(mock_task_id, advance=1)


class TestModeIsolation:
    """Ensure mode changes don't leak between tests."""

    def teardown_method(self):
        set_mode("normal")


class TestVPrintWithArgs:
    """vprint passes through args and kwargs to console.print."""

    def test_vprint_passes_kwargs_in_verbose(self):
        set_mode("verbose")
        with patch.object(progress_module.console, "print") as mock_print:
            vprint("msg", style="bold", highlight=False)
            mock_print.assert_called_once_with("msg", style="bold", highlight=False)

    def test_vprint_does_not_call_console_in_quiet(self):
        set_mode("quiet")
        with patch.object(progress_module.console, "print") as mock_print:
            vprint("msg")
            mock_print.assert_not_called()