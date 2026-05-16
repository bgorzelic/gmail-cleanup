# Contributing

Thanks for taking the time to look at this. This is a small, focused tool — contributions that keep it small and focused are very welcome.

## First-time onboarding (read this if you're new to the repo)

1. **Skim [`README.md`](README.md)** — what the tool does + the one-command flow.
2. **Read [`ARCHITECTURE.md`](ARCHITECTURE.md)** — 5-minute tour of the codebase. Where everything lives, how the layers compose, what NOT to break.
3. **Set up locally** (see "Setup" below) and run `pytest`. If you see `84 passed`, you're good.
4. **Look at [`HANDOFF.md`](HANDOFF.md)** for current open work.
5. **Pick a [Good First Issue](https://github.com/bgorzelic/gmail-cleanup/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)** — or open a discussion before larger changes.

**Cardinal rule:** Read the four safety invariants in `ARCHITECTURE.md` before touching anything in `cmd_unsubscribe`, the `lists/*.yaml` files, or `test_safety.py`. The tool's job is to *never* unsubscribe from a bank.

## Project values

1. **Safety over speed.** The KEEP list, the human whitelist, and the "no List-Unsubscribe header = skip" rule exist because losing a bank alert or archiving a real person's email is unforgivable. PRs that loosen safety for convenience will probably be rejected.
2. **Reversibility.** Archive over delete by default. The user can always recover from All Mail.
3. **Auditability.** Every destructive action should be visible in output. No silent state changes.
4. **Small surface area.** Resist the urge to add a feature flag for every preference. If something can be a YAML edit instead of a CLI flag, prefer the YAML edit.

## Setup

```bash
git clone https://github.com/bgorzelic/gmail-cleanup
cd gmail-cleanup
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

You'll need your own GCP OAuth credentials (`credentials.json` — see `credentials.example.json`) to exercise the live commands. The test suite mocks the Gmail API and does not need credentials.

## Running tests

```bash
pytest                    # full suite
pytest -v                 # verbose
pytest tests/test_safety.py   # one file
```

All new code that touches the safety helpers (`_parse_list_unsubscribe`, `_extract_email`, KEEP-list matching, list loader) **must** have a test. Other features should have a test where practical.

## Code style

- Python 3.11+ features encouraged (match/case, `X | None` unions, `pathlib.Path`, f-strings)
- Type hints on function signatures
- Ruff for lint/format: `ruff check . && ruff format .`
- Line length: 100
- No `black`/`isort`/`flake8` — ruff covers it

## Commit messages

Conventional commits, present tense, imperative mood:

- `feat: add verify subcommand`
- `fix: handle empty List-Unsubscribe header`
- `docs: clarify KEEP list semantics in README`
- `refactor: extract list loader`
- `test: cover quoted display names in _extract_email`
- `chore: bump dependencies`

## Adding entries to the shipped lists

The YAML files in `lists/` ship with the project. If you're proposing additions:

- **`kill.yaml`** — only domains/senders confirmed to be pure noise (newsletters, marketing, job spam). If there's any chance someone might want the sender's mail, it doesn't belong here.
- **`keep.yaml`** — only categorically critical senders (banks, healthcare, .gov, security/account-protection). Err generous; false positives are intentional.
- **`humans.yaml`** — personal whitelists shouldn't ship in the project default. Leave it empty in the repo's default; users add their own.
- **`unsubbed.yaml`** — user-state, not project-state. Should ship empty in the default.

(The current repo defaults reflect the maintainer's own inbox during initial development. Before v1.0 we'll factor these into a project default + user override.)

## Pull requests

- One concern per PR. A new feature + a refactor in the same PR is hard to review.
- If you're adding a CLI flag, also add an entry to the README command table.
- If you're changing safety-critical logic, link the test that proves the new behavior.

## Reporting bugs

Open an issue with:

- What you ran (full command line)
- What you expected
- What actually happened (with `--dry-run` output if relevant)
- OS + Python version

For anything involving the safety lists or accidental loss of mail, include the failed step exactly so we can patch the regression with a test.
