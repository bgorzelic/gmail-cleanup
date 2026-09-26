import json
from unittest.mock import MagicMock, patch

from gmail_cleanup.notify import notify_if_configured, send_autopilot_notification


class TestSendAutopilotNotification:
    """Tests for send_autopilot_notification using mocked urllib."""

    def test_posts_json_to_webhook_url(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch('gmail_cleanup.notify.urllib.request.urlopen', return_value=mock_resp) as mock_open:
            send_autopilot_notification(
                'https://hooks.example.com/notify',
                'a@example.com',
                dry_run=True,
                escalate=False,
                trigger='manual',
            )

        req = mock_open.call_args[0][0]
        assert req.full_url == 'https://hooks.example.com/notify'
        assert req.get_header('Content-type') == 'application/json'
        assert req.get_method() == 'POST'

        body = json.loads(req.data)
        assert body['event'] == 'autopilot_finished'
        assert body['email'] == 'a@example.com'
        assert body['dry_run'] is True
        assert body['escalate'] is False
        assert body['trigger'] == 'manual'
        assert 'finished_at' in body

    def test_success_does_not_raise(self):
        mock_resp = MagicMock()
        mock_resp.status = 204
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch('gmail_cleanup.notify.urllib.request.urlopen', return_value=mock_resp):
            send_autopilot_notification('https://hooks.example.com/ok', 'x@y.com')

    def test_network_error_does_not_raise(self):
        with patch(
            'gmail_cleanup.notify.urllib.request.urlopen',
            side_effect=ConnectionError('refused'),
        ):
            send_autopilot_notification('https://hooks.example.com/bad', 'x@y.com')

    def test_timeout_does_not_raise(self):
        import urllib.error

        with patch(
            'gmail_cleanup.notify.urllib.request.urlopen',
            side_effect=urllib.error.URLError('timed out'),
        ):
            send_autopilot_notification('https://hooks.example.com/slow', 'x@y.com')


class TestNotifyIfConfigured:
    """Tests for the notify_if_configured dispatcher."""

    def test_noop_when_no_notify_key(self):
        with patch('gmail_cleanup.notify.send_autopilot_notification') as mock_send:
            notify_if_configured({}, 'a@example.com')
            mock_send.assert_not_called()

    def test_noop_when_webhook_url_none(self):
        with patch('gmail_cleanup.notify.send_autopilot_notification') as mock_send:
            notify_if_configured({'notify': {'webhook_url': None}}, 'a@example.com')
            mock_send.assert_not_called()

    def test_noop_when_webhook_url_empty(self):
        with patch('gmail_cleanup.notify.send_autopilot_notification') as mock_send:
            notify_if_configured({'notify': {'webhook_url': ''}}, 'a@example.com')
            mock_send.assert_not_called()

    def test_calls_send_when_url_set(self):
        cfg = {'notify': {'webhook_url': 'https://hooks.example.com/go'}}
        with patch('gmail_cleanup.notify.send_autopilot_notification') as mock_send:
            notify_if_configured(cfg, 'a@example.com', dry_run=True, escalate=True, trigger='scheduled')
            mock_send.assert_called_once_with(
                'https://hooks.example.com/go',
                'a@example.com',
                dry_run=True,
                escalate=True,
                trigger='scheduled',
            )

    def test_handles_missing_notify_dict(self):
        cfg = {'default_email': 'x'}
        with patch('gmail_cleanup.notify.send_autopilot_notification') as mock_send:
            notify_if_configured(cfg, 'a@example.com')
            mock_send.assert_not_called()
