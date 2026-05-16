import os
from pathlib import Path

import pytest

from gmail_cleanup.config import load_config


@pytest.fixture
def isolated_env(monkeypatch, tmp_path):
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('GMAIL_CLEANUP_CONFIG', raising=False)
    home = Path(os.environ['HOME'])
    (home / '.gmail_cli').mkdir(parents=True, exist_ok=True)
    return tmp_path


class TestLoadConfig:
    def test_returns_defaults_when_no_config(self, isolated_env):
        cfg = load_config()
        assert cfg['default_email'] is None
        assert cfg['accounts'] == []
        assert cfg['defaults']['unsubscribe']['days'] == 30
        assert cfg['defaults']['unsubscribe']['min_count'] == 2
        assert cfg['defaults']['verify']['days'] == 14
        assert cfg['defaults']['account_timeout'] == 300

    def test_loads_canonical_location(self, isolated_env):
        cfg_path = isolated_env / 'home' / '.gmail_cli' / 'config.yaml'
        cfg_path.write_text("default_email: you@gmail.com\n")
        cfg = load_config()
        assert cfg['default_email'] == 'you@gmail.com'

    def test_env_var_overrides_canonical(self, isolated_env, monkeypatch):
        custom = isolated_env / 'custom.yaml'
        custom.write_text("default_email: custom@example.com\n")
        monkeypatch.setenv('GMAIL_CLEANUP_CONFIG', str(custom))
        (isolated_env / 'home' / '.gmail_cli' / 'config.yaml').write_text(
            "default_email: home@example.com\n"
        )
        assert load_config()['default_email'] == 'custom@example.com'

    def test_cwd_fallback(self, isolated_env):
        (isolated_env / 'gmail-cleanup.yaml').write_text(
            "default_email: cwd@example.com\n"
        )
        assert load_config()['default_email'] == 'cwd@example.com'

    def test_accounts_list_parses(self, isolated_env):
        (isolated_env / 'home' / '.gmail_cli' / 'config.yaml').write_text("""
accounts:
  - email: a@example.com
    label: personal
  - email: b@example.com
    label: work
""")
        cfg = load_config()
        assert len(cfg['accounts']) == 2
        assert cfg['accounts'][0]['email'] == 'a@example.com'
        assert cfg['accounts'][1]['label'] == 'work'

    def test_partial_defaults_merge(self, isolated_env):
        (isolated_env / 'home' / '.gmail_cli' / 'config.yaml').write_text("""
defaults:
  unsubscribe:
    days: 60
""")
        cfg = load_config()
        assert cfg['defaults']['unsubscribe']['days'] == 60
        assert cfg['defaults']['unsubscribe']['min_count'] == 2
        assert cfg['defaults']['verify']['days'] == 14

    def test_malformed_yaml_raises_clear_error(self, isolated_env):
        (isolated_env / 'home' / '.gmail_cli' / 'config.yaml').write_text(
            "default_email: : :\n"
        )
        with pytest.raises(ValueError, match='Could not parse'):
            load_config()

    def test_top_level_list_rejected(self, isolated_env):
        (isolated_env / 'home' / '.gmail_cli' / 'config.yaml').write_text(
            "- foo\n- bar\n"
        )
        with pytest.raises(ValueError, match='must be a YAML mapping'):
            load_config()
