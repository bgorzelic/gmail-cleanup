"""Gmail API usage: idempotent calls retry with backoff; status stays cheap."""

from argparse import Namespace
from unittest.mock import MagicMock

import gmail_cleanup as gmail_cli


def _client(service):
    gmail = gmail_cli.GmailCLI.__new__(gmail_cli.GmailCLI)
    gmail.service = service
    gmail.user_email = 'me@example.com'
    return gmail


def test_search_messages_retries_with_backoff():
    service = MagicMock()
    request = service.users().messages().list.return_value
    request.execute.return_value = {'messages': [{'id': '1'}]}
    service.users().messages().list_next.return_value = None

    assert _client(service).search_messages('in:inbox') == [{'id': '1'}]
    request.execute.assert_called_with(num_retries=gmail_cli.API_RETRIES)


def test_send_is_not_retried():
    # A retried send could deliver a duplicate unsubscribe email.
    service = MagicMock()
    _client(service).send_message('list@example.com', 'unsubscribe')
    service.users().messages().send.return_value.execute.assert_called_once_with()


def test_status_uses_one_label_call_not_message_paging(monkeypatch, capsys):
    service = MagicMock()
    service.users().labels().get.return_value.execute.return_value = {
        'threadsTotal': 3933, 'threadsUnread': 3516,
    }
    gmail = _client(service)
    monkeypatch.setattr(gmail_cli, 'GmailCLI', lambda email: gmail)
    monkeypatch.setattr(gmail_cli, '_list_filters', lambda g: [])

    gmail_cli.cmd_status(Namespace(email='me@example.com'))

    service.users().labels().get.assert_called_with(userId='me', id='INBOX')
    service.users().messages().list.assert_not_called()
    out = capsys.readouterr().out
    assert '3,933' in out and '3,516' in out
