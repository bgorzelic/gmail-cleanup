"""Account-list management for gmail-cleanup multi-account support."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from gmail_cleanup.config import find_config_file, init_config


def _config_path_or_init() -> Path:
    """Return the config file path, initializing if needed."""
    path = find_config_file()
    if path is None:
        path = init_config()
    return path


def _load_raw_config() -> Dict[str, Any]:
    """Load config file's raw dict (without merging defaults)."""
    path = _config_path_or_init()
    with open(path, encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a YAML mapping")
    return data


def _save_raw_config(data: Dict[str, Any]) -> None:
    """Save raw config dict back to file."""
    path = _config_path_or_init()
    path.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))


def list_accounts() -> List[Dict[str, Any]]:
    """List all configured accounts."""
    return list(_load_raw_config().get('accounts') or [])


def add_account(email: str, label: Optional[str] = None) -> Dict[str, Any]:
    """Add or replace an account entry. Returns the stored record."""
    data = _load_raw_config()
    accounts = [a for a in (data.get('accounts') or []) if a.get('email') != email]
    record: Dict[str, Any] = {'email': email}
    if label:
        record['label'] = label
    accounts.append(record)
    data['accounts'] = accounts
    _save_raw_config(data)
    return record


def remove_account(email: str) -> bool:
    """Remove account by email. Returns True if removed, False if not present."""
    data = _load_raw_config()
    accounts = list(data.get('accounts') or [])
    new_accounts = [a for a in accounts if a.get('email') != email]
    if len(new_accounts) == len(accounts):
        return False
    data['accounts'] = new_accounts
    _save_raw_config(data)
    return True
