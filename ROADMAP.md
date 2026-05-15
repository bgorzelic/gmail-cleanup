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

## Path to v1.0 (public-ready)

In rough order:

1. **Lists as data, not code.** Move `VETTED_KILL_LIST`, `UNSUB_KEEP_LIST`, `HUMANS_WHITELIST`, `UNSUBBED_SENDERS` to YAML in `lists/`. Users edit without touching source; lists are diff-able and shareable.
2. **Test suite.** Pytest coverage on safety-critical helpers (`_parse_list_unsubscribe`, `_humans_exclusion`, `_extract_email`, KEEP-list enforcement). Mock the Gmail API.
3. **Block-filter fallback.** When a sender's unsubscribe fails twice across runs, auto-create a Gmail filter that trashes them. Closes the loop on stuck unsubs.
4. **Stickiness verification command.** `verify` subcommand: diff current top-senders against the unsubscribe log, flag senders that should be silent but aren't.
5. **Packaging.** `pyproject.toml`, `pip install -e .` works, console script entry point `gmail-cleanup`. Drop the `.py` from invocation.
6. **README polish + screenshots/asciinema.** Public-facing first impression.
7. **CONTRIBUTING.md + CODE_OF_CONDUCT.md.** Standard OSS hygiene.

## Open questions

None blocking.
