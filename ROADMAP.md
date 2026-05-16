# Roadmap

This is the working prototype for a productized email-management toolset. The notes below are direction-setting, not commitments.

## v0.5.0 — ✅ DONE (2026-05-15)

Eight new components shipped. All items below were completed:

1. ✅ **Config file.** `~/.gmail_cli/config.yaml` with deep-merge defaults, env-var override, CWD fallback. `config show / init` subcommands.
2. ✅ **Multi-account support.** `accounts list / add / remove`. `--all-accounts` flag on `autopilot`, `stats`, `verify`.
3. ✅ **Auto-close-the-loop.** Successful unsubs auto-append to `lists/unsubbed.yaml` via atomic-write helper.
4. ✅ **`attachments` subcommand.** Oversized email finder, sender-by-bytes ranking, `--archive` / `--delete` with confirmation.
5. ✅ **`status` dashboard.** Live Gmail counts, filter inventory, list sizes, 7-day history.
6. ✅ **`schedule` subcommand.** Daily launchd autopilot on macOS (`install / uninstall / status`).
7. ✅ **`setup` wizard.** 6-step interactive flow. Reduces first-run friction by ~80%.
8. ✅ **Rich progress UI + global flags.** `--quiet` (cron-safe), `--verbose` (debug). Per-account state file with 30-entry history cap.
9. ✅ **Package refactor.** `gmail_cli.py` → `gmail_cleanup/` package. Console script entry unchanged.
10. ✅ **Tests.** 84 passing (up from 52; +32 covering config, accounts, state, lists_io, attachments, multi-account dispatch).

## Productization direction (decided 2026-05-15)

**Standalone OSS CLI.** MIT licensed. Polish → public GitHub → PyPI as `gmail-cleanup`. Lead-gen for `inbox-detox` SaaS, not folded into it.

Rejected directions (for the record): umbrella suite (premature, no second tool yet), folding into SaaS (loses OSS/technical audience), core-library + multi-frontend (too much upfront for one shipped frontend).

## Path to v1.0 (public-ready) — ✅ DONE

All seven items shipped in v0.3.0:

1. ✅ **Lists as data, not code.** → `lists/*.yaml` + `_load_list()` (commit: `feat: extract lists to YAML`)
2. ✅ **Test suite.** → 46 pytest tests across `_load_list`, header parsers, KEEP-list semantics
3. ✅ **Block-filter fallback.** → `_create_block_filter()` helper, used by `verify --escalate`
4. ✅ **Stickiness verification command.** → `verify` subcommand with `--since` and `--escalate`
5. ✅ **Packaging.** → `pyproject.toml`, `pip install -e .` installs the `gmail-cleanup` console script
6. ✅ **README polish.** → Rewritten with the new entry point + safety-model table linking to lists/
7. ✅ **CONTRIBUTING + CODE_OF_CONDUCT.** → Both shipped at the repo root

The repo is publish-quality. When you push to GitHub public, no further polish is required for a credible v1.0 announcement.

## gws note

`github.com/googleworkspace/cli` is a candidate API layer if the suite expands to a second tool (Calendar, Drive, etc.). The Go-based CLI provides a unified Google Workspace interface that could complement `gmail-cleanup`'s Python core. Decision deferred to tool #2 — no reason to evaluate it until there's a concrete use case. `gmail-cleanup` stays Python.

## Post-v0.5 ideas

These are spec §14 out-of-scope items carried forward, plus new ideas — none are blockers.

- **`asciinema` demo** embedded in README. The cleanest first impression for a CLI.
- **Project-default vs. user-override list separation.** Current `lists/*.yaml` mix project defaults (kill list, keep-list categories) with user state (humans, unsubbed). Split into `lists/defaults/*.yaml` (shipped) and `~/.gmail_cli/lists/*.yaml` (user) with a merge step in `_load_list`.
- **PyPI publish.** Once external users have run it on their inbox without surprises, ship to PyPI so `pip install gmail-cleanup` works for everyone.
- **GitHub Actions CI.** Lint + test on every PR. Cheap and standard.
- **`verify` schema upgrade.** Move `lists/unsubbed.yaml` to a richer schema (`{sender, unsubscribed_at}`) so `verify` can compute per-sender windows automatically instead of relying on `--since`.
- **Windows `schedule` support.** v0.5 scheduler is macOS-only (launchd). Task Scheduler equivalent for Windows users.
- **Notification hooks.** Post-autopilot summary to Slack / Telegram / email. Useful for `--all-accounts` multi-account runs.

## Open questions

- Push to public GitHub? (One command away: `gh repo create bgorzelic/gmail-cleanup --public --source=. --push`.)
