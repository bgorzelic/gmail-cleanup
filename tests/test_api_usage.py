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


class _FakeBatch:
    """Stands in for BatchHttpRequest: answers each sub-request via `responder`."""

    def __init__(self, callback, responder, log):
        self.callback, self.responder, self.log = callback, responder, log
        self.ids = []

    def add(self, request, request_id):
        self.ids.append(request_id)

    def execute(self):
        self.log.append(list(self.ids))
        for mid in self.ids:
            response, exception = self.responder(mid)
            self.callback(mid, response, exception)


def _http_error(status, content=b''):
    from googleapiclient.errors import HttpError
    resp = MagicMock(status=status, reason='x')
    return HttpError(resp, content)


def _batching_client(monkeypatch, responder):
    monkeypatch.setattr(gmail_cli.time, 'sleep', lambda s: None)
    service = MagicMock()
    log = []
    service.new_batch_http_request.side_effect = (
        lambda callback: _FakeBatch(callback, responder, log)
    )
    return _client(service), log


def test_metadata_fetch_batches_in_chunks_of_50(monkeypatch):
    gmail, log = _batching_client(monkeypatch, lambda mid: ({'id': mid}, None))
    ids = [str(i) for i in range(120)]
    ticks = []
    result = gmail.get_messages_metadata(ids, ['From'], on_progress=lambda: ticks.append(1))
    assert [len(b) for b in log] == [50, 50, 20]
    assert set(result) == set(ids)
    assert len(ticks) == 120


def test_rate_limited_messages_are_retried(monkeypatch):
    seen = {}

    def responder(mid):
        seen[mid] = seen.get(mid, 0) + 1
        if mid == 'b' and seen[mid] == 1:
            return None, _http_error(429)
        return {'id': mid}, None

    gmail, log = _batching_client(monkeypatch, responder)
    result = gmail.get_messages_metadata(['a', 'b'], ['From'])
    assert set(result) == {'a', 'b'}
    assert log == [['a', 'b'], ['b']]


def test_non_retryable_errors_are_skipped_and_reported(monkeypatch, capsys):
    gmail, log = _batching_client(
        monkeypatch, lambda mid: (None, _http_error(404)) if mid == 'gone' else ({'id': mid}, None)
    )
    result = gmail.get_messages_metadata(['a', 'gone'], ['From'])
    assert set(result) == {'a'}
    assert len(log) == 1
    assert '1 message(s) could not be fetched' in capsys.readouterr().out


def test_retryable_error_gives_up_after_api_retries(monkeypatch):
    gmail, log = _batching_client(monkeypatch, lambda mid: (None, _http_error(503)))
    assert gmail.get_messages_metadata(['a'], ['From']) == {}
    assert len(log) == gmail_cli.API_RETRIES + 1


def test_403_rate_limit_is_retryable_but_plain_403_is_not():
    assert gmail_cli._is_retryable(_http_error(403, b'{"reason": "userRateLimitExceeded"}'))
    assert not gmail_cli._is_retryable(_http_error(403, b'{"reason": "forbidden"}'))
