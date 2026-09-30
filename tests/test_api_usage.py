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


def test_metadata_fetch_batches_in_chunks(monkeypatch):
    gmail, log = _batching_client(monkeypatch, lambda mid: ({'id': mid}, None))
    ids = [str(i) for i in range(60)]
    ticks = []
    result = gmail.get_messages_metadata(ids, ['From'], on_progress=lambda: ticks.append(1))
    assert [len(b) for b in log] == [25, 25, 10]
    assert set(result) == set(ids)
    assert len(ticks) == 60


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


def _rate_error(status=429, content=b'', retry_after=None):
    from googleapiclient.errors import HttpError
    resp = MagicMock(status=status, reason='x')
    resp.get.side_effect = lambda k, d=None: retry_after if k == 'retry-after' else d
    return HttpError(resp, content)


def test_quota_exceeded_403_counts_as_rate_limit():
    assert gmail_cli._is_rate_limit(_rate_error(403, b'{"reason": "quotaExceeded"}'))
    assert gmail_cli._is_rate_limit(_rate_error(403, b'{"reason": "userRateLimitExceeded"}'))
    assert not gmail_cli._is_rate_limit(_rate_error(403, b'{"reason": "insufficientPermissions"}'))


def test_retry_after_header_wins_and_is_capped():
    assert gmail_cli._retry_delay(_rate_error(retry_after='42'), 0) == 42
    assert gmail_cli._retry_delay(_rate_error(retry_after='99999'), 0) == gmail_cli.MAX_RETRY_AFTER


def test_rate_limit_backoff_is_slower_than_server_error_backoff():
    rate = [gmail_cli._retry_delay(_rate_error(429), n) for n in range(6)]
    assert 5 <= rate[0] < 6 and 10 <= rate[1] < 11
    assert 80 <= rate[5] < 81  # capped
    server = [gmail_cli._retry_delay(_rate_error(503), n) for n in range(6)]
    assert 1 <= server[0] < 2 and 10 <= server[5] < 11


def test_retries_use_smaller_batches(monkeypatch):
    seen = {}

    def responder(mid):
        seen[mid] = seen.get(mid, 0) + 1
        return (None, _rate_error(429)) if seen[mid] == 1 else ({'id': mid}, None)

    gmail, log = _batching_client(monkeypatch, responder)
    ids = [str(i) for i in range(25)]
    assert set(gmail.get_messages_metadata(ids, ['From'])) == set(ids)
    assert [len(b) for b in log] == [25, 10, 10, 5]


def test_rate_limit_is_remembered_and_expires(monkeypatch):
    gmail, _ = _batching_client(monkeypatch, lambda mid: (None, _rate_error(429, retry_after='120')))
    assert gmail_cli.rate_limited_until('me@example.com') is None
    gmail.get_messages_metadata(['a'], ['From'])
    until = gmail_cli.rate_limited_until('me@example.com')
    assert until is not None

    gmail_cli.record_rate_limit('me@example.com', -5)  # already in the past
    assert gmail_cli.rate_limited_until('me@example.com') is None


def test_autopilot_skips_while_rate_limited(monkeypatch, capsys):
    gmail_cli.record_rate_limit('me@example.com', 600)
    ran = []
    monkeypatch.setattr(gmail_cli, 'cmd_filters', lambda ns: ran.append('filters'))
    gmail_cli.cmd_autopilot(Namespace(email='me@example.com', dry_run=False, escalate=False))
    assert ran == []
    assert 'rate-limited' in capsys.readouterr().out
