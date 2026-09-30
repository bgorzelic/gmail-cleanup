"""autopilot wiring: unsubscribe thresholds and the optional emailed report."""

from argparse import Namespace
from unittest.mock import MagicMock

import pytest

import gmail_cleanup as gmail_cli


@pytest.fixture
def phases(monkeypatch):
    """Stub every phase; record the Namespace each one receives."""
    calls = {}

    def recorder(name, output=''):
        def fn(ns):
            calls[name] = ns
            if output:
                print(output)
        return fn

    monkeypatch.setattr(gmail_cli, 'cmd_filters', recorder('filters'))
    monkeypatch.setattr(gmail_cli, 'cmd_unsubscribe', recorder('unsubscribe', 'Total: 3 senders'))
    monkeypatch.setattr(gmail_cli, 'cmd_mark_read', recorder('mark_read'))
    monkeypatch.setattr(gmail_cli, 'cmd_verify', recorder('verify'))
    monkeypatch.setattr(gmail_cli, 'cmd_stats', recorder('stats'))
    gmail = MagicMock()
    gmail.send_message.return_value = True
    monkeypatch.setattr(gmail_cli, 'GmailCLI', lambda email: gmail)
    calls['gmail'] = gmail
    return calls


def _args(**overrides):
    base = dict(email='me@example.com', dry_run=True, escalate=False,
                days=30, min_count=2, email_summary=False)
    return Namespace(**{**base, **overrides})


def test_thresholds_reach_unsubscribe_phase(phases):
    gmail_cli.cmd_autopilot(_args(days=7, min_count=1))
    assert phases['unsubscribe'].days == 7
    assert phases['unsubscribe'].min_count == 1


def test_no_email_without_flag(phases):
    gmail_cli.cmd_autopilot(_args())
    phases['gmail'].send_message.assert_not_called()


def test_email_summary_sends_report_to_self(phases, capsys):
    gmail_cli.cmd_autopilot(_args(email_summary=True))
    to, subject, body = phases['gmail'].send_message.call_args.args
    assert to == 'me@example.com'
    assert 'dry run' in subject
    assert 'Total: 3 senders' in body
    # Output still reaches the terminal while being captured.
    assert 'Total: 3 senders' in capsys.readouterr().out


def test_email_failure_does_not_raise(phases):
    phases['gmail'].send_message.side_effect = RuntimeError('network down')
    gmail_cli.cmd_autopilot(_args(email_summary=True))


def test_stdout_restored_when_a_phase_fails(phases, monkeypatch):
    import sys

    def boom(ns):
        raise RuntimeError('phase failed')

    monkeypatch.setattr(gmail_cli, 'cmd_unsubscribe', boom)
    before = sys.stdout
    with pytest.raises(RuntimeError):
        gmail_cli.cmd_autopilot(_args(email_summary=True))
    assert sys.stdout is before
    phases['gmail'].send_message.assert_not_called()
