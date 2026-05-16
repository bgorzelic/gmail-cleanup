"""Config file loader for gmail-cleanup.

Lookup order (first match wins):
  1. $GMAIL_CLEANUP_CONFIG env var
  2. ~/.gmail_cli/config.yaml
  3. ./gmail-cleanup.yaml (CWD)

Returns a dict with all keys filled in (deep-merged with built-in defaults).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    'default_email': None,
    'accounts': [],
    'lists_dir': None,
    'defaults': {
        'unsubscribe': {'days': 30, 'min_count': 2},
        'verify': {'days': 14},
        'account_timeout': 300,
    },
}


def config_search_paths() -> list[Path]:
    """Return config search paths in order of precedence."""
    paths: list[Path] = []
    env_path = os.getenv('GMAIL_CLEANUP_CONFIG')
    if env_path:
        paths.append(Path(env_path).expanduser())
    paths.append(Path.home() / '.gmail_cli' / 'config.yaml')
    paths.append(Path.cwd() / 'gmail-cleanup.yaml')
    return paths


def find_config_file() -> Path | None:
    """Find the first existing config file in search paths."""
    for p in config_search_paths():
        if p.is_file():
            return p
    return None


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overrides into base dict."""
    out = dict(base)
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict[str, Any]:
    """Load config from file or return defaults if no file found.

    Returns:
        Dict with all keys present (merged with built-in defaults).

    Raises:
        ValueError: If config file is malformed YAML or not a mapping.
    """
    path = find_config_file()
    if not path:
        return _deep_merge({}, DEFAULTS)
    try:
        with open(path) as f:
            user = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Could not parse {path}: {e}") from e
    if user is None:
        user = {}
    if not isinstance(user, dict):
        raise ValueError(
            f"{path} must be a YAML mapping (got {type(user).__name__})"
        )
    return _deep_merge(DEFAULTS, user)
