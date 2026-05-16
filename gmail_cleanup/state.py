"""Per-account state file at ~/.gmail_cli/state_<email>.json.

Records autopilot/unsubscribe/mark-read events for the `status` command to
summarize. History capped at 30 entries.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HISTORY_MAX = 30


def _path(email: str) -> Path:
    safe = email.replace('/', '_').replace('\\', '_')
    return Path.home() / '.gmail_cli' / f'state_{safe}.json'


def read_state(email: str) -> dict[str, Any]:
    path = _path(email)
    if not path.exists():
        return {
            'history': [],
            'last_autopilot_at': None,
            'last_autopilot_source': None,
        }
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {
            'history': [],
            'last_autopilot_at': None,
            'last_autopilot_source': None,
        }


def append_event(email: str, source: str, deltas: dict[str, Any]) -> None:
    state = read_state(email)
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    event = {'at': now, 'source': source, **deltas}
    state.setdefault('history', []).append(event)
    state['history'] = state['history'][-HISTORY_MAX:]
    if source == 'autopilot':
        state['last_autopilot_at'] = now
        state['last_autopilot_source'] = deltas.get('trigger', 'manual')
    path = _path(email)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(path)
