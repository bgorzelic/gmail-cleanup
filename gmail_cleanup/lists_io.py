"""Mutation helpers for lists/*.yaml files."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import yaml

import gmail_cleanup

HEADER_AUTO = (
    "# Auto-managed by gmail-cleanup. Manual edits preserved as long as\n"
    "# file remains a top-level list of strings or mappings.\n"
)

UnsubbedEntry = str | dict


def _read_header_and_body(path: Path) -> tuple[str, list[UnsubbedEntry]]:
    """Read YAML list file and separate header comments from content.

    Returns (header_text, list_of_entries).
    If file doesn't exist, returns (HEADER_AUTO, []).
    """
    if not path.exists():
        return HEADER_AUTO, []
    text = path.read_text()
    header_lines = []
    for line in text.splitlines(keepends=True):
        if line.startswith('#') or line.strip() == '':
            header_lines.append(line)
        else:
            break
    header = ''.join(header_lines) or HEADER_AUTO
    body = yaml.safe_load(text) or []
    if not isinstance(body, list):
        raise ValueError(f"{path}: top-level must be a YAML list")
    return header, body


def _normalize_unsubbed_entry(entry: UnsubbedEntry) -> str:
    """Extract sender string from an unsubbed entry (old or new format)."""
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        sender = entry.get('sender')
        if sender:
            return str(sender).strip()
    return ''


def _load_unsubbed_senders(path: Path) -> list[str]:
    """Load sender strings from unsubbed.yaml, accepting both old and new formats."""
    _, body = _read_header_and_body(path)
    senders = []
    for entry in body:
        sender = _normalize_unsubbed_entry(entry)
        if sender:
            senders.append(sender)
    return senders


def append_to_unsubbed(senders: Iterable[str]) -> list[str]:
    """Append senders to lists/unsubbed.yaml. Returns newly-added entries (idempotent).

    Atomically writes the file using a temp file + rename pattern.
    Deduplicates against existing entries before writing.
    New entries are written in the new mapping format: {sender, unsubscribed_at}.
    """
    path = gmail_cleanup.LISTS_DIR / 'unsubbed.yaml'
    header, existing_entries = _read_header_and_body(path)

    # Build set of existing senders for deduplication
    existing_senders = set()
    for entry in existing_entries:
        sender = _normalize_unsubbed_entry(entry)
        if sender:
            existing_senders.add(sender)

    new_senders = []
    new_entries = []
    now = datetime.now(UTC).isoformat().replace('+00:00', 'Z')

    for s in senders:
        s = s.strip()
        if s and s not in existing_senders:
            existing_senders.add(s)
            new_senders.append(s)
            # Write new entries in mapping format
            new_entries.append({'sender': s, 'unsubscribed_at': now})

    if not new_senders:
        return []

    # Combine existing entries (preserving their format) with new entries (mapping format)
    all_entries = existing_entries + new_entries
    body = yaml.safe_dump(all_entries, default_flow_style=False, sort_keys=False)
    tmp = path.with_suffix('.yaml.tmp')
    tmp.write_text(header + body)
    tmp.replace(path)
    return new_senders


def load_unsubbed_senders() -> list[str]:
    """Load sender strings from lists/unsubbed.yaml, accepting both old and new formats.

    This is the public API for reading the unsubbed list with schema upgrade support.
    """
    path = gmail_cleanup.LISTS_DIR / 'unsubbed.yaml'
    return _load_unsubbed_senders(path)
