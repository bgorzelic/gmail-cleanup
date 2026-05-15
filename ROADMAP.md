# Roadmap

This is the working prototype for a productized email-management toolset. The notes below are direction-setting, not commitments.

## Near-term (next 1–2 sessions)

- **Stickiness verification job.** Cron-style `top-senders --days 14` + diff against the unsubscribe log. Auto-flag senders that should have stopped but didn't.
- **Killlist as YAML.** Move `VETTED_KILL_LIST`, `UNSUB_KEEP_LIST`, `HUMANS_WHITELIST`, and `UNSUBBED_SENDERS` out of source and into a `lists/` directory of YAML files. Users can edit without touching code; lists become diff-able and shareable.
- **Block-filter fallback.** When an unsubscribe fails twice across separate runs, create a Gmail filter that auto-trashes that sender. The current flow gives up on failed unsubs.
- **Test suite.** Pytest coverage on `_parse_list_unsubscribe`, `_humans_exclusion`, `_extract_email`. The Gmail API calls stay mocked.

## Productization candidates

A few directions, not mutually exclusive:

### Direction A — Standalone OSS CLI
Polish, package, publish to PyPI as `gmail-cleanup` or similar.
- **For:** distribution to technical users who want the audit trail and won't accept a hosted service touching their email
- **Against:** OAuth setup friction is the main adoption barrier; users have to create their own GCP project
- **Outcome:** a credibility-building OSS project; lead-gen for the SaaS

### Direction B — `email-utilities` suite
Multiple CLI tools under one umbrella (`gmail-cleanup`, `gmail-export`, `gmail-rules-as-code`, etc.) sharing a common core library.
- **For:** clean separation of concerns, broader surface area for SEO/discovery
- **Against:** premature without a second tool actually built

### Direction C — Folded into `inbox-detox` SaaS
This CLI becomes the implementation layer behind the hosted product.
- **For:** maximum code reuse; the safety model is the product's main moat
- **Against:** loses the technical-user/OSS audience

### Direction D — Core library + multiple frontends
Extract `gmail_core/` library; CLI, agent skill, and SaaS web app all consume it.
- **For:** clean architecture, matches the original inbox-detox plan
- **Against:** more upfront work; pays off only if all three frontends ship

## Open questions

1. License? MIT for OSS distribution, or proprietary if it goes SaaS-only?
2. Naming — keep `gmail-cleanup`, or umbrella as `email-utilities` from day one?
3. Public GitHub repo, or stay private until v1?
4. Relationship to `inbox-detox` — sibling, parent, or child?
