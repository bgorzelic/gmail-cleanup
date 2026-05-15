# Changelog

All notable changes to this project. Format loosely based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [0.2.0] — 2026-05-15

The "filters and verification" pass. Where the tool gained the declarative side.

### Added
- `filters apply` — creates and upgrades Gmail filters in two steps:
  - **Step 1:** finds existing label-only filters and recreates them with `INBOX` removal (so labeled mail also skips inbox)
  - **Step 2:** creates a preset of four high-value filters:
    1. `whitelist-humans` → star + important + spam-protect
    2. `has:list catch-all → 📧 Newsletters` → label + archive + mark read (excludes humans)
    3. `previously-unsubscribed (dated)` → label + archive (anti-resurrection)
    4. `killlist` → label + archive
- `filters list` and `filters delete` subcommands
- `UNSUBBED_SENDERS` constant — tracks the 2026-05-14 unsubscribe cohort so the filter preset can route any resurrection attempts straight to archive
- `_humans_exclusion()` helper — generates a Gmail search fragment that excludes the human whitelist from any aggressive query

### Changed
- OAuth scope list expanded to include `gmail.send` and `gmail.settings.basic` (required for mailto-unsubscribe and filter management respectively)

### Cleanup campaign — Day 2

Performed on `bgorzelic@gmail.com`:

- **Verification of Day 1 unsubscribes:** 17/20 stuck; 3 still sending (localflirt, LinkedIn job alerts, forwardfuture) → flagged for manual escalation
- **Trend analysis:** 1,406 messages analyzed over 14 days, top 30 senders ranked
- **Filter overhaul:** 8 existing label-only filters upgraded to also archive; 4 new preset filters created (total: **12 active filters**, all archiving)
- **GitHub blackout:** 83 GitHub messages archived; future GitHub mail routes to its label automatically
- **Round 2 unsubscribe:** 25 senders one-click unsubscribed, 2 failed, 1 archive-only (no `List-Unsubscribe` header), 61 more inbox messages cleared
- **End state:** inbox at 147 (vs. 7,283 at campaign start = **98% reduction**)

## [0.1.0] — 2026-05-14

Initial cleanup methodology and tooling.

### Added
- `gmail_cli.py` core: OAuth-authenticated Gmail wrapper, per-account token files
- Commands: `stats`, `top-senders`, `subscriptions`, `unsubscribe`, `archive`, `delete`, `label`
- RFC 8058 one-click POST unsubscribe + GET fallback + mailto fallback
- `VETTED_KILL_LIST` — 30+ confirmed noise sender domains
- `UNSUB_KEEP_LIST` — financial, healthcare, government, security senders that the unsubscribe flow refuses to touch
- `HUMANS_WHITELIST` — 10 real correspondents protected from aggressive filters
- Dry-run mode for `unsubscribe`

### Cleanup campaign — Day 1

Performed on `bgorzelic@gmail.com`:

- **Deep sweep:** inbox 7,283 → 1,540 → 33 (selective archival of automation, keeping only human correspondence)
- **Round 1 unsubscribe:** 20 senders one-click unsubscribed via RFC 8058 (all 200 OK at the time of POST)
- **Audit trail:** every action logged for verification at the 2-week mark
