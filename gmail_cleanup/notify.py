"""Webhook notification for autopilot completion.

When ``notify.webhook_url`` is set in config, POSTs a short JSON summary
after autopilot finishes.  Uses only the standard library (urllib).
Failures are logged and never crash autopilot.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

log = logging.getLogger(__name__)

_NOTIFY_TIMEOUT = 10  # seconds


def send_autopilot_notification(
    webhook_url: str,
    email: str,
    *,
    dry_run: bool = False,
    escalate: bool = False,
    trigger: str = 'manual',
) -> None:
    """POST a JSON summary to *webhook_url* after autopilot finishes.

    All exceptions are caught and logged; this must never raise.
    """
    payload: dict[str, Any] = {
        'event': 'autopilot_finished',
        'email': email,
        'dry_run': dry_run,
        'escalate': escalate,
        'trigger': trigger,
        'finished_at': datetime.now(UTC).isoformat(timespec='seconds'),
    }
    body = json.dumps(payload, separators=(',', ':')).encode()
    req = urllib.request.Request(
        webhook_url,
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=_NOTIFY_TIMEOUT) as resp:
            log.info('Webhook notified (%s %s)', resp.status, webhook_url)
    except Exception:
        log.exception('Webhook notification failed for %s', webhook_url)


def notify_if_configured(
    cfg: dict[str, Any],
    email: str,
    *,
    dry_run: bool = False,
    escalate: bool = False,
    trigger: str = 'manual',
) -> None:
    """Send notification if a webhook URL is configured; otherwise no-op."""
    webhook_url = (cfg.get('notify') or {}).get('webhook_url')
    if not webhook_url:
        return
    send_autopilot_notification(
        webhook_url,
        email,
        dry_run=dry_run,
        escalate=escalate,
        trigger=trigger,
    )
