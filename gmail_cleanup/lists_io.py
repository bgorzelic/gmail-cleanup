"""Read/write helpers for the YAML lists (packaged seed + ~/.gmail_cli/lists)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import yaml

import gmail_cleanup
from gmail_cleanup.atomic_io import atomic_write, file_lock

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
    # The header is a block of whole lines, so it has to end with a newline.
    # Without one, a header whose last comment line is unterminated swallows the
    # first entry dumped after it, and that sender is silently lost.
    if not header.endswith('\n'):
        header += '\n'
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


def _seed_path() -> Path:
    return gmail_cleanup.LISTS_DIR / 'unsubbed.yaml'


def _user_path() -> Path:
    return gmail_cleanup.user_lists_dir() / 'unsubbed.yaml'


def append_to_unsubbed(senders: Iterable[str]) -> list[str]:
    """Append senders to ~/.gmail_cli/lists/unsubbed.yaml. Returns newly-added entries.

    Idempotent: deduplicates against the user file and the packaged seed.
    Atomically writes the file using a temp file + rename pattern — the packaged
    seed is never written, so installs into site-packages stay read-only.
    New entries are written in the new mapping format: {sender, unsubscribed_at}.
    """
    path = _user_path()
    # The lock spans the read as well as the write, so two runs appending at
    # once cannot drop each other's senders.
    with file_lock(path):
        header, existing_entries = _read_header_and_body(path)
        existing_senders = {
            sender for sender in map(_normalize_unsubbed_entry, existing_entries) if sender
        }
        existing_senders.update(_load_unsubbed_senders(_seed_path()))
        new_senders = []
        new_entries = []
        now = datetime.now(UTC).isoformat().replace('+00:00', 'Z')
        for s in senders:
            s = s.strip()
            if s and s not in existing_senders:
                existing_senders.add(s)
                new_senders.append(s)
                new_entries.append({'sender': s, 'unsubscribed_at': now})
        if not new_senders:
            return []
        # Existing entries keep their format; new ones use the mapping format.
        body = yaml.safe_dump(
            existing_entries + new_entries, default_flow_style=False, sort_keys=False
        )
        atomic_write(path, header + body)
    return new_senders


def _parse_timestamp(value: object) -> datetime | None:
    """Parse an `unsubscribed_at` value into an aware UTC datetime, or None."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def load_unsubbed_entries() -> list[tuple[str, datetime | None]]:
    """Load (sender, unsubscribed_at) pairs from the seed and user lists, de-duplicated.

    Old-format (bare string) entries have no timestamp and yield None. When a
    sender appears more than once, the latest known timestamp wins.
    """
    merged: dict[str, datetime | None] = {}
    for path in (_seed_path(), _user_path()):
        _, body = _read_header_and_body(path)
        for entry in body:
            sender = _normalize_unsubbed_entry(entry)
            if not sender:
                continue
            ts = _parse_timestamp(entry.get('unsubscribed_at')) if isinstance(entry, dict) else None
            prev = merged.get(sender)
            if sender not in merged or (ts and (prev is None or ts > prev)):
                merged[sender] = ts
    return list(merged.items())


def load_unsubbed_senders() -> list[str]:
    """Load sender strings from the seed and user unsubbed lists (old and new formats)."""
    return [sender for sender, _ in load_unsubbed_entries()]
