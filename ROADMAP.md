# Roadmap

This is the working prototype for a productized email-management toolset. The notes below are direction-setting, not commitments.

## Near-term (next 1–2 sessions)

- **Stickiness verification job.** Cron-style `top-senders --days 14` + diff against the unsubscribe log. Auto-flag senders that should have stopped but didn't.
- **Killlist as YAML.** Move `VETTED_KILL_LIST`, `UNSUB_KEEP_LIST`, `HUMANS_WHITELIST`, and `UNSUBBED_SENDERS` out of source and into a `lists/` directory of YAML files. Users can edit without touching code; lists become diff-able and shareable.
- **Block-filter fallback.** When an unsubscribe fails twice across separate runs, create a Gmail filter that auto-trashes that sender. The current flow gives up on failed unsubs.
- **Test suite.** Pytest coverage on `_parse_list_unsubscribe`, `_humans_exclusion`, `_extract_email`. The Gmail API calls stay mocked.

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

## Post-v1.0 ideas

These are nice-to-haves, not blockers.

- **`asciinema` demo** embedded in README. The cleanest first impression for a CLI.
- **Project-default vs. user-override list separation.** Current `lists/*.yaml` mix project defaults (the kill list, the keep-list categories) with user state (humans, unsubbed). Split into `lists/defaults/*.yaml` (shipped) and `~/.gmail_cli/lists/*.yaml` (user) with a merge step in `_load_list`.
- **Multi-account batch operations.** Run the same command against several accounts in one invocation (`--email a@x.com --email b@y.com`). Useful for the household/family-admin use case.
- **PyPI publish.** Once a couple of external users have run it on their inbox without surprises, ship to PyPI so `pip install gmail-cleanup` works for everyone.
- **GitHub Actions CI.** Lint + test on every PR. Cheap and standard.
- **`verify` schema upgrade.** Move `lists/unsubbed.yaml` to a richer schema (`{sender, unsubscribed_at}`) so `verify` can compute the per-sender window automatically instead of relying on `--since`.

## Open questions

- Push to public GitHub? (One command away: `gh repo create bgorzelic/gmail-cleanup --public --source=. --push`.)
