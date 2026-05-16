"""Tests for append_to_unsubbed() atomic list mutation."""

from pathlib import Path

import pytest

import gmail_cleanup as gmail_cli
from gmail_cleanup.lists_io import append_to_unsubbed


@pytest.fixture
def isolated_lists(monkeypatch, tmp_path):
    """Create a temporary lists directory with a sample unsubbed.yaml."""
    lists_dir = tmp_path / 'lists'
    lists_dir.mkdir()
    (lists_dir / 'unsubbed.yaml').write_text("# header comment\n- foo@example.com\n")
    monkeypatch.setattr(gmail_cli, 'LISTS_DIR', lists_dir)
    return lists_dir


def test_appends_new_sender(isolated_lists):
    """New senders should be added to the list."""
    added = append_to_unsubbed(['bar@example.com'])
    assert added == ['bar@example.com']
    text = (isolated_lists / 'unsubbed.yaml').read_text()
    assert 'foo@example.com' in text
    assert 'bar@example.com' in text


def test_dedupes_existing_sender(isolated_lists):
    """Existing senders should not be re-added (returns empty list)."""
    assert append_to_unsubbed(['foo@example.com']) == []


def test_preserves_top_header_comment(isolated_lists):
    """Header comments should be preserved after append."""
    append_to_unsubbed(['bar@example.com'])
    text = (isolated_lists / 'unsubbed.yaml').read_text()
    assert text.startswith('#')


def test_atomic_write_does_not_corrupt_on_partial_failure(isolated_lists, monkeypatch):
    """File should remain unchanged if write fails (atomic semantics)."""
    original = (isolated_lists / 'unsubbed.yaml').read_text()
    def boom(self, target):
        raise OSError("simulated failure")
    monkeypatch.setattr(Path, 'replace', boom)
    with pytest.raises(OSError):
        append_to_unsubbed(['bar@example.com'])
    assert (isolated_lists / 'unsubbed.yaml').read_text() == original
