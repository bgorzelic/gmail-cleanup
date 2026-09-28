"""Per-account state file at ~/.gmail_cli/state_<email>.json.

Records autopilot/unsubscribe/mark-read events for the `status` command to
summarize. History capped at 30 entries.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gmail_cleanup.atomic_io import atomic_write, file_lock

HISTORY_MAX = 30


def _path(email: str) -> Path:
    safe = email.replace('/', '_').replace('\\', '_')
    return Path.home() / '.gmail_cli' / f'state_{safe}.json'


def _default_state() -> dict[str, Any]:
    return {
        'history': [],
        'last_autopilot_at': None,
        'last_autopilot_source': None,
    }


def _read_state_file(path: Path) -> dict[str, Any]:
    """Load a state file, tolerating content we cannot parse.

    An unreadable state file must never take down a command, so missing and
    undecodable files fall back to the default shape. Other OSError subclasses
    (permissions, a directory in the file's place) still propagate: those are
    misconfigurations a silent reset would hide.
    """
    try:
        text = path.read_text()
    except FileNotFoundError:
        return _default_state()
    except ValueError:  # UnicodeDecodeError — stray non-UTF-8 bytes
        return _default_state()

    try:
        state = json.loads(text)
    except json.JSONDecodeError:
        return _default_state()

    if not isinstance(state, dict):
        return _default_state()
    if not isinstance(state.get('history'), list):
        state['history'] = []
    return state


def read_state(email: str) -> dict[str, Any]:
    return _read_state_file(_path(email))


def append_event(email: str, source: str, deltas: dict[str, Any]) -> None:
    path = _path(email)
    # The lock spans the read as well as the write: a scheduled autopilot and a
    # manual command appending to the same account would otherwise lose events.
    with file_lock(path):
        state = _read_state_file(path)
        now = datetime.now(UTC).isoformat(timespec='seconds')
        # 'at' and 'source' are the record's own fields and win over deltas.
        event = {**deltas, 'at': now, 'source': source}
        state.setdefault('history', []).append(event)
        state['history'] = state['history'][-HISTORY_MAX:]
        if source == 'autopilot':
            state['last_autopilot_at'] = now
            state['last_autopilot_source'] = deltas.get('trigger', 'manual')
        atomic_write(path, json.dumps(state, indent=2))
