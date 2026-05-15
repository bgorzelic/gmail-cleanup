"""Tests for the YAML list loader and the shipped list files."""

import pytest
import yaml

import gmail_cli


class TestLoadList:
    def test_returns_empty_for_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gmail_cli, 'LISTS_DIR', tmp_path)
        assert gmail_cli._load_list('does-not-exist') == []

    def test_loads_simple_list(self, tmp_path, monkeypatch):
        (tmp_path / 'sample.yaml').write_text('- foo\n- bar\n- baz\n')
        monkeypatch.setattr(gmail_cli, 'LISTS_DIR', tmp_path)
        assert gmail_cli._load_list('sample') == ['foo', 'bar', 'baz']

    def test_strips_whitespace_and_skips_empty_entries(self, tmp_path, monkeypatch):
        (tmp_path / 'sample.yaml').write_text("- '  foo  '\n- ''\n- bar\n- '   '\n")
        monkeypatch.setattr(gmail_cli, 'LISTS_DIR', tmp_path)
        assert gmail_cli._load_list('sample') == ['foo', 'bar']

    def test_handles_empty_file(self, tmp_path, monkeypatch):
        (tmp_path / 'sample.yaml').write_text('')
        monkeypatch.setattr(gmail_cli, 'LISTS_DIR', tmp_path)
        assert gmail_cli._load_list('sample') == []

    def test_handles_comments_only_file(self, tmp_path, monkeypatch):
        (tmp_path / 'sample.yaml').write_text('# just a comment\n# nothing else\n')
        monkeypatch.setattr(gmail_cli, 'LISTS_DIR', tmp_path)
        assert gmail_cli._load_list('sample') == []

    def test_rejects_top_level_dict(self, tmp_path, monkeypatch):
        (tmp_path / 'sample.yaml').write_text('foo: bar\nbaz: qux\n')
        monkeypatch.setattr(gmail_cli, 'LISTS_DIR', tmp_path)
        with pytest.raises(ValueError, match='must be a top-level YAML list'):
            gmail_cli._load_list('sample')

    def test_rejects_top_level_string(self, tmp_path, monkeypatch):
        (tmp_path / 'sample.yaml').write_text('"just a string"\n')
        monkeypatch.setattr(gmail_cli, 'LISTS_DIR', tmp_path)
        with pytest.raises(ValueError, match='must be a top-level YAML list'):
            gmail_cli._load_list('sample')


class TestShippedListFiles:
    """Smoke tests on the actual lists/*.yaml files in the repo."""

    def test_kill_list_is_nonempty_and_well_formed(self):
        assert len(gmail_cli.VETTED_KILL_LIST) > 0
        for entry in gmail_cli.VETTED_KILL_LIST:
            assert isinstance(entry, str)
            assert entry == entry.strip()
            assert entry  # no empty strings

    def test_keep_list_protects_critical_categories(self):
        """The KEEP list must shield bank/health/gov/security senders.

        These are the patterns that absolutely have to be in keep.yaml — losing
        any of them would let the unsubscribe flow target a critical sender.
        """
        required_substrings = [
            '.gov',          # any government
            'bank',          # generic banking
            'fidelity',      # brokerage
            'paypal',        # payment
            'navyfederal',   # bank (specific)
            'kaiser',        # healthcare
            'va.gov',        # VA
            'irs.gov',       # IRS
            'accounts.google.com',  # security
        ]
        keep_text = ' '.join(gmail_cli.UNSUB_KEEP_LIST).lower()
        for s in required_substrings:
            assert s in keep_text, f"keep list is missing critical substring: {s!r}"

    def test_humans_whitelist_has_real_emails(self):
        """Humans list should contain things that look like email addresses."""
        assert len(gmail_cli.HUMANS_WHITELIST) > 0
        for entry in gmail_cli.HUMANS_WHITELIST:
            assert '@' in entry, f"humans entry doesn't look like an email: {entry!r}"

    def test_no_duplicate_entries_within_each_list(self):
        for name, lst in [
            ('kill', gmail_cli.VETTED_KILL_LIST),
            ('keep', gmail_cli.UNSUB_KEEP_LIST),
            ('humans', gmail_cli.HUMANS_WHITELIST),
            ('unsubbed', gmail_cli.UNSUBBED_SENDERS),
        ]:
            assert len(lst) == len(set(lst)), f"{name}.yaml contains duplicates"
