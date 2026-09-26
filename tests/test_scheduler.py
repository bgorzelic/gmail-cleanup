"""Tests for the launchd scheduler.

Every test runs fully sandboxed: the module's home-relative path constants are
repointed at `tmp_path`, `Path.home()` itself is monkeypatched, and
`subprocess.run` is replaced with a recorder. No test may write to the real
`~/Library/LaunchAgents`, and no test may invoke the real `launchctl` — the
`sandbox` fixture asserts both of those at teardown.
"""

import platform
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from gmail_cleanup import scheduler

LABEL = 'com.github.bgorzelic.gmail-cleanup'


class LaunchctlRecorder:
    """Stand-in for subprocess.run that records argv and returns a canned result."""

    def __init__(self, returncode: int = 0, stdout: str = '', stderr: str = ''):
        self.calls: list[tuple[list[str], dict]] = []
        self._returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    def __call__(self, args, **kwargs):
        argv = list(args)
        self.calls.append((argv, kwargs))
        return subprocess.CompletedProcess(
            args, self._returncode, stdout=self._stdout, stderr=self._stderr
        )

    @property
    def argvs(self) -> list[list[str]]:
        return [argv for argv, _ in self.calls]


@pytest.fixture(autouse=True)
def pretend_mac(monkeypatch):
    """Default every test to macOS; scheduler is Mac-only and CI runs on Linux."""
    monkeypatch.setattr(platform, 'system', lambda: 'Darwin')


@pytest.fixture
def sandbox(monkeypatch, tmp_path):
    """Redirect every scheduler path and side effect into tmp_path."""
    home = tmp_path / 'home'
    cwd = tmp_path / 'cwd'
    cwd.mkdir(parents=True, exist_ok=True)

    real_plist = Path.home() / 'Library' / 'LaunchAgents' / f'{LABEL}.plist'

    def real_fingerprint() -> tuple[bool, int]:
        try:
            return True, real_plist.stat().st_mtime_ns
        except OSError:
            return False, 0

    real_before = real_fingerprint()

    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setattr(Path, 'home', staticmethod(lambda: home))
    monkeypatch.setattr(
        scheduler,
        'LAUNCHAGENTS_DIR',
        home / 'Library' / 'LaunchAgents',
    )
    monkeypatch.setattr(
        scheduler,
        'PLIST_PATH',
        home / 'Library' / 'LaunchAgents' / f'{LABEL}.plist',
    )
    monkeypatch.setattr(
        scheduler,
        'WRAPPER_PATH',
        home / '.gmail_cli' / 'bin' / 'run-autopilot.sh',
    )
    monkeypatch.setattr(
        scheduler,
        'LOG_DIR',
        home / '.gmail_cli' / 'logs',
    )
    monkeypatch.chdir(cwd)

    # scheduler.subprocess is the real subprocess module, so this both fakes
    # launchctl for the code under test and hard-blocks any accidental real call.
    launchctl = LaunchctlRecorder()
    monkeypatch.setattr(scheduler.subprocess, 'run', launchctl)

    ctx = SimpleNamespace(
        home=home,
        cwd=cwd,
        launchagents=home / 'Library' / 'LaunchAgents',
        plist=home / 'Library' / 'LaunchAgents' / f'{LABEL}.plist',
        wrapper=home / '.gmail_cli' / 'bin' / 'run-autopilot.sh',
        log_dir=home / '.gmail_cli' / 'logs',
        launchctl=launchctl,
    )
    yield ctx

    for path in (ctx.plist, ctx.wrapper):
        assert path.is_relative_to(tmp_path), f'test escaped tmp_path: {path}'
    for argv in launchctl.argvs:
        assert argv[0] == 'launchctl', f'test invoked a real subprocess: {argv}'
    assert real_fingerprint() == real_before, f'test touched the real {real_plist}'


@pytest.fixture
def failed_launchctl(monkeypatch, sandbox):
    """Same sandbox, but launchctl reports failure."""
    launchctl = LaunchctlRecorder(returncode=1, stdout='', stderr='Load failed: 5: Input/output error')
    monkeypatch.setattr(scheduler.subprocess, 'run', launchctl)
    return launchctl


class TestModulePaths:
    def test_constants_derive_from_home(self, monkeypatch, tmp_path):
        """Module constants are computed from Path.home() at import time."""
        import importlib.util

        fake_home = tmp_path / 'fake-home'
        monkeypatch.setattr(Path, 'home', staticmethod(lambda: fake_home))
        spec = importlib.util.spec_from_file_location(
            'gmail_cleanup._scheduler_probe', Path(scheduler.__file__)
        )
        probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probe)

        assert probe.PLIST_LABEL == LABEL
        expected = (
            fake_home / 'Library' / 'LaunchAgents',
            fake_home / 'Library' / 'LaunchAgents' / f'{LABEL}.plist',
            fake_home / '.gmail_cli' / 'bin' / 'run-autopilot.sh',
            fake_home / '.gmail_cli' / 'logs',
        )
        actual = (
            probe.LAUNCHAGENTS_DIR,
            probe.PLIST_PATH,
            probe.WRAPPER_PATH,
            probe.LOG_DIR,
        )
        assert actual == expected
        assert not fake_home.exists(), 'importing the module must not create files'


class TestEnsureMac:
    def test_passes_silently_on_darwin(self, sandbox, capsys):
        assert scheduler.ensure_mac() is None
        assert capsys.readouterr().out == ''

    @pytest.mark.parametrize('system', ['Linux', 'Windows'])
    def test_exits_on_non_darwin(self, sandbox, capsys, monkeypatch, system):
        monkeypatch.setattr(platform, 'system', lambda: system)
        with pytest.raises(SystemExit) as exc:
            scheduler.ensure_mac()
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert 'Mac-only' in out
        assert 'Linux/Windows planned for v0.6' in out


class TestInstall:
    def test_writes_wrapper_and_plist(self, sandbox):
        scheduler.install('me@example.com', '07:30', escalate=False)

        wrapper = sandbox.wrapper.read_text()
        assert wrapper.startswith('#!/bin/bash\n')
        assert 'set -euo pipefail' in wrapper
        assert 'export GMAIL_CLEANUP_SCHEDULED=1' in wrapper
        assert 'starting autopilot for me@example.com' in wrapper
        assert wrapper.rstrip().endswith('autopilot  --quiet')

        plist = sandbox.plist.read_text()
        assert '<key>Label</key>' in plist
        assert f'<string>{LABEL}</string>' in plist
        assert f'<string>{sandbox.wrapper}</string>' in plist
        assert '<key>Hour</key>\n        <integer>7</integer>' in plist
        assert '<key>Minute</key>\n        <integer>30</integer>' in plist
        assert '<key>RunAtLoad</key>\n    <false/>' in plist

    def test_creates_directories(self, sandbox):
        assert not sandbox.log_dir.exists()
        assert not sandbox.wrapper.parent.exists()
        scheduler.install('me@example.com', '07:30', escalate=False)
        assert sandbox.log_dir.is_dir()
        assert sandbox.wrapper.parent.is_dir()
        assert sandbox.launchagents.is_dir()

    def test_wrapper_is_executable(self, sandbox):
        scheduler.install('me@example.com', '07:30', escalate=False)
        assert stat.S_IMODE(sandbox.wrapper.stat().st_mode) == 0o755

    def test_escalate_flag_added(self, sandbox):
        scheduler.install('me@example.com', '07:30', escalate=True)
        assert 'autopilot --escalate --quiet' in sandbox.wrapper.read_text()

    def test_no_escalate_flag_by_default(self, sandbox):
        scheduler.install('me@example.com', '07:30', escalate=False)
        assert '--escalate' not in sandbox.wrapper.read_text()

    def test_uses_venv_binary_when_present(self, sandbox):
        venv_bin = sandbox.cwd / '.venv' / 'bin' / 'gmail-cleanup'
        venv_bin.parent.mkdir(parents=True)
        venv_bin.write_text('#!/bin/sh\n')
        scheduler.install('me@example.com', '07:30', escalate=False)
        assert f'exec {venv_bin} --email me@example.com autopilot' in sandbox.wrapper.read_text()

    def test_falls_back_to_path_binary(self, sandbox):
        scheduler.install('me@example.com', '07:30', escalate=False)
        assert 'exec gmail-cleanup --email me@example.com autopilot' in sandbox.wrapper.read_text()

    @pytest.mark.parametrize(
        'time_hhmm,hour,minute',
        [('00:00', 0, 0), ('07:30', 7, 30), ('9:05', 9, 5), ('23:59', 23, 59)],
    )
    def test_time_parsed_into_hour_and_minute(self, sandbox, time_hhmm, hour, minute):
        scheduler.install('me@example.com', time_hhmm, escalate=False)
        plist = sandbox.plist.read_text()
        assert f'<integer>{hour}</integer>' in plist
        assert f'<integer>{minute}</integer>' in plist

    def test_launches_via_launchctl_unload_then_load(self, sandbox):
        scheduler.install('me@example.com', '07:30', escalate=False)
        assert sandbox.launchctl.argvs == [
            ['launchctl', 'unload', str(sandbox.plist)],
            ['launchctl', 'load', str(sandbox.plist)],
        ]

    def test_print_summary(self, sandbox, capsys):
        scheduler.install('me@example.com', '07:30', escalate=False)
        out = capsys.readouterr().out
        assert 'Scheduled autopilot for me@example.com at 07:30 daily' in out
        assert f'plist:   {sandbox.plist}' in out
        assert f'wrapper: {sandbox.wrapper}' in out
        assert f'logs:    {sandbox.log_dir}/autopilot-YYYY-MM-DD.log' in out

    def test_exits_on_non_darwin_without_side_effects(self, sandbox, capsys, monkeypatch):
        monkeypatch.setattr(platform, 'system', lambda: 'Linux')
        with pytest.raises(SystemExit) as exc:
            scheduler.install('me@example.com', '07:30', escalate=False)
        assert exc.value.code == 1
        assert sandbox.launchctl.calls == []
        assert not sandbox.plist.exists()
        assert not sandbox.wrapper.exists()
        assert not sandbox.log_dir.exists()
        assert 'Mac-only' in capsys.readouterr().out

    def test_refuses_to_overwrite_existing_plist(self, sandbox, capsys):
        sandbox.plist.parent.mkdir(parents=True)
        sandbox.plist.write_text('ORIGINAL')
        with pytest.raises(SystemExit) as exc:
            scheduler.install('me@example.com', '07:30', escalate=False)
        assert exc.value.code == 1
        assert sandbox.plist.read_text() == 'ORIGINAL'
        assert not sandbox.wrapper.exists()
        assert sandbox.launchctl.calls == []
        out = capsys.readouterr().out
        assert 'already at' in out
        assert '--force' in out
        assert 'schedule uninstall' in out

    def test_force_overwrites_existing_plist(self, sandbox):
        sandbox.plist.parent.mkdir(parents=True)
        sandbox.plist.write_text('ORIGINAL')
        scheduler.install('me@example.com', '07:30', escalate=False, force=True)
        assert 'ORIGINAL' not in sandbox.plist.read_text()
        assert LABEL in sandbox.plist.read_text()
        assert sandbox.launchctl.argvs[-1] == ['launchctl', 'load', str(sandbox.plist)]

    def test_warns_when_launchctl_load_fails(self, sandbox, capsys, failed_launchctl):
        scheduler.install('me@example.com', '07:30', escalate=False)
        out = capsys.readouterr().out
        assert 'launchctl load failed' in out
        assert 'Input/output error' in out
        assert 'Scheduled autopilot for me@example.com' in out
        assert sandbox.plist.exists()
        assert failed_launchctl.argvs[-1] == ['launchctl', 'load', str(sandbox.plist)]

    def test_launchctl_calls_capture_output(self, sandbox):
        scheduler.install('me@example.com', '07:30', escalate=False)
        unload_kwargs, load_kwargs = (kwargs for _, kwargs in sandbox.launchctl.calls)
        assert unload_kwargs['capture_output'] is True
        assert load_kwargs['capture_output'] is True
        assert load_kwargs['text'] is True


class TestUninstall:
    def test_removes_plist_and_unloads(self, sandbox, capsys):
        scheduler.install('me@example.com', '07:30', escalate=False)
        capsys.readouterr()
        scheduler.uninstall()

        assert not sandbox.plist.exists()
        assert sandbox.launchctl.argvs[-1] == ['launchctl', 'unload', str(sandbox.plist)]
        assert 'Scheduled job removed' in capsys.readouterr().out

    def test_reports_when_nothing_installed(self, sandbox, capsys):
        scheduler.uninstall()
        out = capsys.readouterr().out
        assert 'No scheduled job at' in out
        assert str(sandbox.plist) in out
        assert sandbox.launchctl.calls == []

    def test_leaves_wrapper_in_place(self, sandbox):
        scheduler.install('me@example.com', '07:30', escalate=False)
        scheduler.uninstall()
        assert sandbox.wrapper.exists(), 'wrapper is intentionally not deleted'

    def test_exits_on_non_darwin_and_keeps_plist(self, sandbox, capsys, monkeypatch):
        monkeypatch.setattr(platform, 'system', lambda: 'Linux')
        sandbox.plist.parent.mkdir(parents=True)
        sandbox.plist.write_text('KEEP')
        with pytest.raises(SystemExit) as exc:
            scheduler.uninstall()
        assert exc.value.code == 1
        assert sandbox.plist.read_text() == 'KEEP'
        assert sandbox.launchctl.calls == []
        assert 'Mac-only' in capsys.readouterr().out


class TestStatus:
    def test_reports_when_nothing_installed(self, sandbox, capsys):
        scheduler.status()
        out = capsys.readouterr().out
        assert 'No scheduled job' in out
        assert 'gmail-cleanup schedule install' in out
        assert sandbox.launchctl.calls == []

    def test_prints_paths_and_loaded_state(self, sandbox, capsys, monkeypatch):
        scheduler.install('me@example.com', '07:30', escalate=False)
        capsys.readouterr()
        monkeypatch.setattr(
            scheduler.subprocess,
            'run',
            LaunchctlRecorder(returncode=0, stdout='{\n  "PID" = 1234;\n}'),
        )
        scheduler.status()

        out = capsys.readouterr().out
        assert f'Plist:   {sandbox.plist}' in out
        assert f'Wrapper: {sandbox.wrapper}' in out
        assert f'Logs:    {sandbox.log_dir}' in out
        assert '"PID" = 1234;' in out
        assert 'not loaded' not in out

    def test_warns_when_not_loaded(self, sandbox, capsys, monkeypatch):
        scheduler.install('me@example.com', '07:30', escalate=False)
        capsys.readouterr()
        monkeypatch.setattr(
            scheduler.subprocess,
            'run',
            LaunchctlRecorder(returncode=113, stdout='', stderr='Could not find service'),
        )
        scheduler.status()
        assert 'not loaded' in capsys.readouterr().out

    def test_queries_launchctl_list_with_label(self, sandbox, monkeypatch):
        recorder = LaunchctlRecorder()
        monkeypatch.setattr(scheduler.subprocess, 'run', recorder)
        scheduler.install('me@example.com', '07:30', escalate=False)
        recorder.calls.clear()
        scheduler.status()
        assert recorder.argvs == [['launchctl', 'list', LABEL]]

    def test_exits_on_non_darwin(self, sandbox, monkeypatch):
        monkeypatch.setattr(platform, 'system', lambda: 'Linux')
        with pytest.raises(SystemExit) as exc:
            scheduler.status()
        assert exc.value.code == 1
        assert sandbox.launchctl.calls == []
