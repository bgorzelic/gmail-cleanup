# gmail-cleanup

## What this is

`gmail-cleanup` is a Python 3.11+ command-line tool for safely reclaiming Gmail inboxes through one-click unsubscribe, declarative filters, bulk inbox operations, and scheduled autopilot. Its central invariant is that protected senders such as banks, government services, and healthcare providers must never be unsubscribed, while archive is preferred over deletion so actions remain recoverable.

## Setup / install

For development:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Live Gmail commands require a Google Cloud project with the Gmail API enabled and local OAuth credentials. The test suite mocks the Gmail API and does not require credentials.

For an end-user installation, the README recommends:

```bash
pipx install git+https://github.com/bgorzelic/gmail-cleanup.git
```

## Build / test / lint

No standalone local build command is documented. The package uses Hatchling as its build backend.

Run the full test suite:

```bash
pytest
```

Useful test variants documented by the project are:

```bash
pytest -v
pytest tests/test_safety.py
```

Lint and format with Ruff:

```bash
ruff check .
ruff format .
```

CI installs `.[dev]`, runs `pytest -q` on Python 3.11, 3.12, and 3.13, and runs `ruff check .` as an advisory check.

## Code style / conventions

- Use Python 3.11+ features, type hints on function signatures, `pathlib.Path`, f-strings, and `X | None` union syntax.
- Ruff is the formatter and linter; the configured line length is 100 and the target version is Python 3.11. Do not introduce Black, isort, or Flake8.
- Preserve the documented safety priorities: safety over speed, archive over delete, visible destructive actions, and a small feature surface.
- Read `ARCHITECTURE.md` and its four safety invariants before changing `cmd_unsubscribe`, `lists/*.yaml`, or `tests/test_safety.py`.
- New code touching `_parse_list_unsubscribe`, `_extract_email`, KEEP-list matching, or the list loader must include tests. Test other features where practical.
- Keep pull requests to one concern. When adding a CLI flag, update the README command table; when changing safety-critical logic, identify the test proving the behavior.

## Working with multiple agents here

- Multiple parallel Claude Code or Codex agents can work on this repository through this machine's `launch-agents` tool. Each agent receives its own git worktree automatically; do not create branches manually for that orchestration workflow.
- On a multi-agent task, check the shared coordination database for file claims before editing any file another agent might be touching. Claim the intended files through the established coordination mechanism before editing them.
- Use the repository's established conventional-commit style in present-tense, imperative mood, such as `feat: add verify subcommand`, `fix: handle empty header`, or `docs: clarify KEEP semantics`.
- Never commit secrets. The current `.gitignore` explicitly covers `credentials.json`, `*.pkl`, `.gmail_cli/`, and `token_*`, but it does **not** cover `.env` or general credential-file patterns. Confirm ignore coverage for the exact secret file before creating it, and never assume an `.env` file is safe merely because it is local.
- Before live Gmail testing, coordinate account-impacting actions and prefer `--dry-run`; destructive commands otherwise prompt unless `--yes` is supplied.

## Sources

This contract was grounded on 2026-08-05 in the repository's `README.md`, `pyproject.toml`, `requirements.txt`, `HANDOFF.md`, `CONTRIBUTING.md`, `.gitignore`, `.github/workflows/test.yml`, top-level tree, and recent git commit subjects.
