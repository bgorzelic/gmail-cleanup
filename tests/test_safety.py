"""Safety-net tests: the substring-match semantics that protect critical senders.

These tests lock down the contract: any sender matching the KEEP list is
shielded from auto-unsubscribe. If this regresses, the tool could silently
unsubscribe a user from their bank's fraud alerts.
"""

import gmail_cli


def _is_protected(sender: str) -> bool:
    """Mirror the protection check used inside cmd_unsubscribe.

    Kept in sync with the substring-match in gmail_cli.cmd_unsubscribe at the
    `keep_hit = next(...)` line. If that logic changes, this helper must update.
    """
    return any(k in sender for k in gmail_cli.UNSUB_KEEP_LIST)


class TestKeepListShieldsCriticalSenders:
    """A sender that matches anything in keep.yaml must be protected."""

    def test_navy_federal(self):
        assert _is_protected('notice@email.navyfederal.org')

    def test_chase_bank(self):
        assert _is_protected('alerts@notifyalert.chase.com')

    def test_fidelity(self):
        assert _is_protected('fidelity.investments@mail.fidelity.com')

    def test_paypal(self):
        assert _is_protected('service@paypal.com')

    def test_venmo(self):
        assert _is_protected('no-reply@venmo.com')

    def test_irs(self):
        assert _is_protected('alert@irs.gov')

    def test_va_government(self):
        assert _is_protected('appointment@va.gov')

    def test_kaiser_health(self):
        assert _is_protected('autoresponse-ncal@kp.org')

    def test_google_security(self):
        assert _is_protected('no-reply@accounts.google.com')

    def test_generic_dot_gov(self):
        # Any .gov should be protected even if not enumerated specifically.
        assert _is_protected('noreply@nasa.gov')

    def test_github_account_or_security(self):
        # GitHub kept because its unsub links require login.
        assert _is_protected('noreply@github.com')
        assert _is_protected('notifications@github.com')


class TestKeepListDoesNotOverShield:
    """Pure noise senders must NOT match the KEEP list."""

    def test_marketing_newsletter(self):
        assert not _is_protected('dan@tldrnewsletter.com')

    def test_job_spam(self):
        assert not _is_protected('jobalerts@sites.careerbuilder.com')

    def test_dating_spam(self):
        assert not _is_protected('support@localflirt.com')

    def test_restaurant_marketing(self):
        assert not _is_protected('offers@m.popeyes.com')

    def test_random_substack_writer(self):
        assert not _is_protected('mollysoshea@substack.com')


class TestUnsubbedSendersAllProtectedFromResurrection:
    """Every sender in unsubbed.yaml should be route-able via the filter preset.

    The preset filter `from: <unsubbed senders OR'd>` matches against the
    sender header. We just need to verify the list isn't empty and entries
    look like email addresses.
    """

    def test_list_is_nonempty(self):
        assert len(gmail_cli.UNSUBBED_SENDERS) > 0

    def test_entries_look_like_emails(self):
        for entry in gmail_cli.UNSUBBED_SENDERS:
            assert '@' in entry, f"unsubbed entry doesn't look like an email: {entry!r}"
