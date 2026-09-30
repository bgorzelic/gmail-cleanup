"""verify only counts mail that proves an unsubscribe did not stick."""

from datetime import UTC, datetime, timedelta

from gmail_cleanup import VERIFY_GRACE_DAYS, _verify_query

NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)
WINDOW_START = NOW - timedelta(days=14)


def _after(query: str) -> datetime:
    return datetime.fromtimestamp(int(query.rsplit('after:', 1)[1]), UTC)


def test_legacy_entry_uses_plain_window():
    query = _verify_query('a@example.com', None, WINDOW_START, NOW)
    assert query.startswith('from:a@example.com ')
    assert _after(query) == WINDOW_START


def test_recent_unsubscribe_is_pending():
    # Unsubscribed yesterday: its pre-unsubscribe mail must not count as "stuck".
    assert _verify_query('a@example.com', NOW - timedelta(days=1), WINDOW_START, NOW) is None


def test_counts_only_mail_after_grace_period():
    unsubbed = NOW - timedelta(days=5)
    query = _verify_query('a@example.com', unsubbed, WINDOW_START, NOW)
    assert _after(query) == unsubbed + timedelta(days=VERIFY_GRACE_DAYS)


def test_old_unsubscribe_still_bounded_by_window():
    unsubbed = NOW - timedelta(days=90)
    query = _verify_query('a@example.com', unsubbed, WINDOW_START, NOW)
    assert _after(query) == WINDOW_START


def test_custom_grace_days():
    unsubbed = NOW - timedelta(days=5)
    assert _verify_query('a@example.com', unsubbed, WINDOW_START, NOW, grace_days=7) is None
    query = _verify_query('a@example.com', unsubbed, WINDOW_START, NOW, grace_days=0)
    assert _after(query) == unsubbed


def test_escalate_never_blocks_pending_senders(monkeypatch, tmp_path):
    from argparse import Namespace
    from unittest.mock import MagicMock

    import gmail_cleanup as gmail_cli

    just_now = datetime.now(UTC).isoformat()
    user = tmp_path / 'user'
    user.mkdir()
    (user / 'unsubbed.yaml').write_text(
        f"- sender: fresh@example.com\n  unsubscribed_at: '{just_now}'\n"
        "- legacy@example.com\n"
    )
    seed = tmp_path / 'seed'
    seed.mkdir()
    monkeypatch.setattr(gmail_cli, 'LISTS_DIR', seed)
    monkeypatch.setattr(gmail_cli, 'user_lists_dir', lambda: user)

    gmail = MagicMock()
    gmail.search_messages.return_value = [{'id': '1'}]  # every queried sender "still arriving"
    monkeypatch.setattr(gmail_cli, 'GmailCLI', lambda email: gmail)
    blocked = []
    monkeypatch.setattr(gmail_cli, '_create_block_filter', lambda g, s: blocked.append(s) or True)

    gmail_cli.cmd_verify(Namespace(email='me@example.com', days=14, since=None, limit=100,
                                   escalate=True, grace_days=VERIFY_GRACE_DAYS))

    queried = [call.args[0] for call in gmail.search_messages.call_args_list]
    assert not any('fresh@example.com' in q for q in queried)
    assert blocked == ['legacy@example.com']
