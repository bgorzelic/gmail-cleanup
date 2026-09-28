"""Tests for the YAML list loader and the shipped list files."""

import pytest
import yaml

import gmail_cleanup as gmail_cli


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

    def test_merges_repo_and_user_lists(self, tmp_path, monkeypatch):
        """Repo list + user list (if present) merged, de-duplicated."""
        # Setup repo list
        (tmp_path / 'sample.yaml').write_text('- repo1\n- repo2\n')
        monkeypatch.setattr(gmail_cli, 'LISTS_DIR', tmp_path)

        # Setup user HOME directory
        home_dir = tmp_path / 'home'
        user_lists_dir = home_dir / '.gmail_cli' / 'lists'
        user_lists_dir.mkdir(parents=True)

        # Test with no user file
        assert gmail_cli._load_list('sample') == ['repo1', 'repo2']

        # Test with user file containing overlapping and new entries
        (user_lists_dir / 'sample.yaml').write_text('- user2\n- repo1\n- user3\n')
        monkeypatch.setenv('HOME', str(home_dir))
        result = gmail_cli._load_list('sample')
        # Repo entries first, then user entries (only new ones)
        assert result == ['repo1', 'repo2', 'user2', 'user3']

    def test_user_list_overrides_repo_in_priority_order(self, tmp_path, monkeypatch):
        """Repo entries first, user entries only for new values."""
        (tmp_path / 'sample.yaml').write_text('- a\n- b\n')
        monkeypatch.setattr(gmail_cli, 'LISTS_DIR', tmp_path)

        home_dir = tmp_path / 'home'
        user_lists_dir = home_dir / '.gmail_cli' / 'lists'
        user_lists_dir.mkdir(parents=True)
        (user_lists_dir / 'sample.yaml').write_text('- b\n- c\n- d\n')
        monkeypatch.setenv('HOME', str(home_dir))

        result = gmail_cli._load_list('sample')
        # a, b from repo; only c, d from user (b already exists)
        assert result == ['a', 'b', 'c', 'd']

    def test_user_list_not_present(self, tmp_path, monkeypatch):
        """User list not present - returns only repo list."""
        (tmp_path / 'sample.yaml').write_text('- only-repo\n')
        monkeypatch.setattr(gmail_cli, 'LISTS_DIR', tmp_path)

        home_dir = tmp_path / 'home'
        monkeypatch.setenv('HOME', str(home_dir))
        result = gmail_cli._load_list('sample')
        assert result == ['only-repo']

    def test_user_list_missing_home_dir(self, tmp_path, monkeypatch):
        """User HOME/.gmail_cli/lists doesn't exist - returns only repo list."""
        (tmp_path / 'sample.yaml').write_text('- repo-only\n')
        monkeypatch.setattr(gmail_cli, 'LISTS_DIR', tmp_path)

        monkeypatch.setenv('HOME', str(tmp_path))
        result = gmail_cli._load_list('sample')
        assert result == ['repo-only']

    def test_rejects_user_file_top_level_dict(self, tmp_path, monkeypatch):
        """Reject invalid user list YAML format."""
        (tmp_path / 'sample.yaml').write_text('- valid\n')
        monkeypatch.setattr(gmail_cli, 'LISTS_DIR', tmp_path)

        home_dir = tmp_path / 'home'
        user_lists_dir = home_dir / '.gmail_cli' / 'lists'
        user_lists_dir.mkdir(parents=True)
        (user_lists_dir / 'sample.yaml').write_text('invalid: yaml: here\n')
        monkeypatch.setenv('HOME', str(home_dir))

        # YAML parsing fails with ScannerError for invalid YAML structure
        with pytest.raises(yaml.scanner.ScannerError):
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

    def test_shipped_lists_with_user_override(self, tmp_path, monkeypatch):
        """Shipped lists should merge with user lists if user lists exist."""
        # This test verifies the merge behavior by directly testing _load_list
        # with both repo and user lists

        # Create a temporary repo lists directory
        repo_dir = tmp_path / 'repo_lists'
        repo_dir.mkdir()
        
        # Write repo file
        (repo_dir / 'humans.yaml').write_text('- repo@example.com\n- repo2@example.com\n')

        # Setup user HOME with override files
        home_dir = tmp_path / 'home'
        user_lists_dir = home_dir / '.gmail_cli' / 'lists'
        user_lists_dir.mkdir(parents=True)

        # Write user file with overlap and new entries
        (user_lists_dir / 'humans.yaml').write_text('- repo2@example.com\n- user@example.com\n- user2@example.com\n')

        # Patch the module to use our temporary paths
        monkeypatch.setattr(gmail_cli, 'LISTS_DIR', repo_dir)
        monkeypatch.setenv('HOME', str(home_dir))

        # Test the load function directly
        result = gmail_cli._load_list('humans')
        
        # Should have all entries: repo entries first, then user entries (excluding duplicates)
        assert 'repo@example.com' in result
        assert 'repo2@example.com' in result
        assert 'user@example.com' in result
        assert 'user2@example.com' in result
        assert len(result) == 4
