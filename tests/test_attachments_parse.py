"""Tests for attachment size parsing."""

import pytest

from gmail_cleanup import _build_attachments_query, _parse_size


def test_parses_mb():
    assert _parse_size("10mb") == 10 * 1024 * 1024
    assert _parse_size("10MB") == 10 * 1024 * 1024


def test_parses_gb():
    assert _parse_size("1gb") == 1024 * 1024 * 1024


def test_parses_kb():
    assert _parse_size("500kb") == 500 * 1024


def test_bare_int_treated_as_bytes():
    assert _parse_size("1024") == 1024


def test_invalid_raises():
    with pytest.raises(ValueError, match="Could not parse size"):
        _parse_size("huge")


def test_attachments_query_excludes_starred_and_important_by_default():
    assert _build_attachments_query("10mb", 180, include_protected=False) == (
        "has:attachment larger:10M -is:starred -is:important older_than:180d"
    )


def test_attachments_query_can_include_protected_mail():
    assert _build_attachments_query("10mb", 180, include_protected=True) == (
        "has:attachment larger:10M older_than:180d"
    )


def test_attachments_query_allows_no_age_filter():
    assert _build_attachments_query("500kb", None, include_protected=False) == (
        "has:attachment larger:500K -is:starred -is:important"
    )
