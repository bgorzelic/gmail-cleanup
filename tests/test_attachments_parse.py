"""Tests for attachment size parsing."""

import pytest
from gmail_cleanup import _parse_size


def test_parses_mb():
    assert _parse_size('10mb') == 10 * 1024 * 1024
    assert _parse_size('10MB') == 10 * 1024 * 1024


def test_parses_gb():
    assert _parse_size('1gb') == 1024 * 1024 * 1024


def test_parses_kb():
    assert _parse_size('500kb') == 500 * 1024


def test_bare_int_treated_as_bytes():
    assert _parse_size('1024') == 1024


def test_invalid_raises():
    with pytest.raises(ValueError, match='Could not parse size'):
        _parse_size('huge')
