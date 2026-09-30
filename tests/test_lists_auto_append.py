"""Tests for append_to_unsubbed() atomic list mutation and schema upgrade."""

from pathlib import Path

import pytest

import gmail_cleanup as gmail_cli
from gmail_cleanup.lists_io import append_to_unsubbed, load_unsubbed_senders


@pytest.fixture
def isolated_lists(monkeypatch, tmp_path):
    """Create a temporary lists directory with a sample unsubbed.yaml."""
    lists_dir = tmp_path / 'lists'
    lists_dir.mkdir()
    (lists_dir / 'unsubbed.yaml').write_text("# header comment\n- foo@example.com\n")
    monkeypatch.setattr(gmail_cli, 'LISTS_DIR', lists_dir)
    # Seed and user lists share one directory here; test_lists_layout.py covers the split.
    monkeypatch.setattr(gmail_cli, 'user_lists_dir', lambda: lists_dir)
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


def test_new_entries_use_mapping_format(isolated_lists):
    """New entries should be written in {sender, unsubscribed_at} mapping format."""
    append_to_unsubbed(['new@example.com'])
    text = (isolated_lists / 'unsubbed.yaml').read_text()
    # Old entry remains as string
    assert '- foo@example.com' in text
    # New entry is a mapping with sender and unsubscribed_at
    assert 'sender: new@example.com' in text
    assert 'unsubscribed_at:' in text


def test_load_unsubbed_senders_reads_old_format(isolated_lists):
    """load_unsubbed_senders should read plain string entries (old format)."""
    senders = load_unsubbed_senders()
    assert senders == ['foo@example.com']


def test_load_unsubbed_senders_reads_new_format(isolated_lists):
    """load_unsubbed_senders should read mapping entries (new format)."""
    # Write a file with new format entries
    (isolated_lists / 'unsubbed.yaml').write_text(
        "# header\n"
        "- sender: mapped@example.com\n"
        "  unsubscribed_at: '2026-01-01T00:00:00Z'\n"
    )
    senders = load_unsubbed_senders()
    assert senders == ['mapped@example.com']


def test_load_unsubbed_senders_reads_mixed_format(isolated_lists):
    """load_unsubbed_senders should read mixed old and new format entries."""
    (isolated_lists / 'unsubbed.yaml').write_text(
        "# header\n"
        "- old@example.com\n"
        "- sender: new@example.com\n"
        "  unsubscribed_at: '2026-01-01T00:00:00Z'\n"
    )
    senders = load_unsubbed_senders()
    assert senders == ['old@example.com', 'new@example.com']


def test_load_unsubbed_senders_empty_file(tmp_path, monkeypatch):
    """load_unsubbed_senders should return empty list for empty/missing file."""
    lists_dir = tmp_path / 'lists'
    lists_dir.mkdir()
    (lists_dir / 'unsubbed.yaml').write_text("# header only\n")
    monkeypatch.setattr(gmail_cli, 'LISTS_DIR', lists_dir)
    monkeypatch.setattr(gmail_cli, 'user_lists_dir', lambda: lists_dir)
    assert load_unsubbed_senders() == []


def test_load_unsubbed_senders_missing_file(tmp_path, monkeypatch):
    """load_unsubbed_senders should return empty list for missing file."""
    lists_dir = tmp_path / 'lists'
    lists_dir.mkdir()
    # No unsubbed.yaml file
    monkeypatch.setattr(gmail_cli, 'LISTS_DIR', lists_dir)
    monkeypatch.setattr(gmail_cli, 'user_lists_dir', lambda: lists_dir)
    assert load_unsubbed_senders() == []


def test_append_preserves_existing_mapping_entries(isolated_lists):
    """Existing mapping-format entries should be preserved when appending."""
    # Start with a mapping entry
    (isolated_lists / 'unsubbed.yaml').write_text(
        "# header\n"
        "- sender: existing@example.com\n"
        "  unsubscribed_at: '2026-01-01T00:00:00Z'\n"
    )
    append_to_unsubbed(['new@example.com'])
    text = (isolated_lists / 'unsubbed.yaml').read_text()
    # Original mapping preserved
    assert 'sender: existing@example.com' in text
    assert 'unsubscribed_at: \'2026-01-01T00:00:00Z\'' in text
    # New entry added as mapping
    assert 'sender: new@example.com' in text
    assert 'unsubscribed_at:' in text


def test_append_dedupes_against_mapping_entries(isolated_lists):
    """Deduplication should work against mapping-format entries."""
    (isolated_lists / 'unsubbed.yaml').write_text(
        "# header\n"
        "- sender: existing@example.com\n"
        "  unsubscribed_at: '2026-01-01T00:00:00Z'\n"
    )
    # Try to add the same sender - should be deduplicated
    added = append_to_unsubbed(['existing@example.com'])
    assert added == []
