"""Mutation helpers for lists/*.yaml files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple

import yaml

import gmail_cleanup

HEADER_AUTO = (
    "# Auto-managed by gmail-cleanup. Manual edits preserved as long as\n"
    "# file remains a top-level list of strings.\n"
)


def _read_header_and_body(path: Path) -> Tuple[str, list[str]]:
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
    return header, [str(x).strip() for x in body if x]


def append_to_unsubbed(senders: Iterable[str]) -> list[str]:
    """Append senders to lists/unsubbed.yaml. Returns newly-added entries (idempotent).

    Atomically writes the file using a temp file + rename pattern.
    Deduplicates against existing entries before writing.
    """
    path = gmail_cleanup.LISTS_DIR / 'unsubbed.yaml'
    header, existing = _read_header_and_body(path)
    existing_set = set(existing)
    new = []
    for s in senders:
        s = s.strip()
        if s and s not in existing_set:
            existing.append(s)
            existing_set.add(s)
            new.append(s)
    if not new:
        return []
    body = yaml.safe_dump(existing, default_flow_style=False, sort_keys=False)
    tmp = path.with_suffix('.yaml.tmp')
    tmp.write_text(header + body)
    tmp.replace(path)
    return new
