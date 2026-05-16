"""Tests for the small helper functions that parse Gmail headers and build queries."""

import pytest

import gmail_cleanup as gmail_cli


class TestExtractEmail:
    def test_extracts_from_name_angle_bracket_form(self):
        assert gmail_cli._extract_email('Brian <foo@example.com>') == 'foo@example.com'

    def test_handles_bare_email(self):
        assert gmail_cli._extract_email('foo@example.com') == 'foo@example.com'

    def test_lowercases(self):
        assert gmail_cli._extract_email('Brian <Foo@Example.COM>') == 'foo@example.com'

    def test_strips_whitespace(self):
        assert gmail_cli._extract_email('  foo@example.com  ') == 'foo@example.com'
        assert gmail_cli._extract_email('Brian <  foo@example.com  >') == 'foo@example.com'

    def test_handles_quoted_display_name(self):
        assert gmail_cli._extract_email('"Brian, Sr." <foo@example.com>') == 'foo@example.com'

    def test_returns_empty_for_empty_input(self):
        assert gmail_cli._extract_email('') == ''


class TestParseListUnsubscribe:
    def test_parses_mailto(self):
        result = gmail_cli._parse_list_unsubscribe('<mailto:unsub@example.com>')
        assert result == [('mailto', 'unsub@example.com')]

    def test_parses_https(self):
        result = gmail_cli._parse_list_unsubscribe('<https://example.com/unsub?id=1>')
        assert result == [('https', 'https://example.com/unsub?id=1')]

    def test_parses_both_mailto_and_https(self):
        result = gmail_cli._parse_list_unsubscribe(
            '<https://example.com/u>, <mailto:unsub@example.com>'
        )
        assert ('https', 'https://example.com/u') in result
        assert ('mailto', 'unsub@example.com') in result

    def test_handles_http_scheme(self):
        result = gmail_cli._parse_list_unsubscribe('<http://example.com/unsub>')
        assert result == [('https', 'http://example.com/unsub')]

    def test_strips_whitespace(self):
        result = gmail_cli._parse_list_unsubscribe('< mailto:unsub@example.com >')
        assert result == [('mailto', 'unsub@example.com')]

    def test_ignores_other_schemes(self):
        result = gmail_cli._parse_list_unsubscribe('<ftp://example.com/unsub>')
        assert result == []

    def test_returns_empty_for_empty_input(self):
        assert gmail_cli._parse_list_unsubscribe('') == []
        assert gmail_cli._parse_list_unsubscribe(None) == []

    def test_returns_empty_for_malformed(self):
        # No angle brackets — not a List-Unsubscribe value at all.
        assert gmail_cli._parse_list_unsubscribe('mailto:unsub@example.com') == []


class TestHumansExclusion:
    def test_produces_negated_from_filter(self):
        result = gmail_cli._humans_exclusion()
        assert result.startswith('-from:(')
        assert result.endswith(')')

    def test_includes_every_human(self):
        result = gmail_cli._humans_exclusion()
        for human in gmail_cli.HUMANS_WHITELIST:
            assert human in result

    def test_uses_or_between_humans(self):
        # Real humans list is large; just check at least one OR appears when there's >1 entry.
        if len(gmail_cli.HUMANS_WHITELIST) > 1:
            assert ' OR ' in gmail_cli._humans_exclusion()
