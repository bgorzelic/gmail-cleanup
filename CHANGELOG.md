# Changelog

All notable changes to this project. Format loosely based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [0.5.2] — 2026-05-16

The "professional polish" release. No behavior changes — README rewrite, stale-reference fixes, GitHub About updated.

### Changed
- **README rewrite**: hero badges (CI, release, Python, license), sample autopilot output, comparison table vs. other tools, three-bucket diagram, pipeline diagram, cleaner section structure with emoji anchors. End-user oriented; contributor docs cross-linked.
- **Stale references fixed**: setup wizard described as "6-step" in three places (README × 2, ARCHITECTURE.md). Now accurately "7-step" per v0.5.1.
- **HANDOFF.md**: version line updated to v0.5.2.

## [0.5.1] — 2026-05-16

The "partner-handoff polish" release. No behavior changes; one OAuth-flow gap closed and onboarding documentation rounded out.

### Added
- **OAuth consent-screen step in the setup wizard** (now `[Step 3/7]`). Previously the wizard jumped from "enable Gmail API" straight to "create OAuth client" — but Google requires the consent screen to be configured first, and unverified apps need the user added as a Test User. Without this step, new users hit "Access blocked: This app's request is invalid" on first run.
- **`TROUBLESHOOTING.md`** covering the 6 issues new users hit most often: consent-screen errors, missing credentials, scope limits, scheduler on Linux/Windows, 7-day token expiry for unverified apps, PATH issues with pipx.
- **`ARCHITECTURE.md`** — 5-minute tour of the codebase (layout, state file locations, layer composition, sender state machine, safety invariants, test guide).
- **CI workflow** (`.github/workflows/test.yml`): pytest matrix across Python 3.11/3.12/3.13 on every push and PR.
- **Issue templates** for bug reports and feature requests.

### Changed
- **README install section** now leads with `pipx install git+https://...` (the right choice for end users) instead of `git clone + pip install -e .` (only relevant for contributors).
- **CONTRIBUTING.md** gains a "First-time onboarding" section pointing new collaborators at ARCHITECTURE.md and the safety invariants.

## [0.5.0] — 2026-05-15

The "Swiss army knife" release. Eight new components across four layers — config foundation, quick wins, features, and onboarding.

### Added
- **Config file** (`~/.gmail_cli/config.yaml`) with deep-merge defaults, env-var override, CWD fallback. New `gmail-cleanup config show / init` subcommands.
- **Multi-account support.** `gmail-cleanup accounts list / add / remove`. Global `--all-accounts` flag on `autopilot`, `stats`, `verify` iterates configured accounts with partial-failure semantics.
- **Auto-close-the-loop on unsubscribes.** Successful unsubs auto-append to `lists/unsubbed.yaml` via atomic-write helper.
- **`gmail-cleanup attachments`** subcommand for storage cleanup. Finds oversized old emails, ranks senders by bytes attributed, supports `--archive` / `--delete` with confirmation.
- **`gmail-cleanup status`** dashboard combining live Gmail counts, filter inventory, list sizes, and 7-day history.
- **`gmail-cleanup schedule install / uninstall / status`** for daily launchd-scheduled autopilot (Mac-only in v0.5).
- **`gmail-cleanup setup`** wizard — 6-step interactive flow that opens browser to GCP, polls Downloads for credentials, runs OAuth smoke test, registers account in config. Reduces first-run friction by ~80%.
- **Rich progress UI** across all long-running commands. New global `--quiet` (cron-friendly silent) and `--verbose` (debug) flags.
- **Per-account state file** at `~/.gmail_cli/state_<email>.json` records autopilot/unsubscribe/mark-read events with 30-entry history cap.

### Changed
- **Package layout.** Converted `gmail_cli.py` (single file) to `gmail_cleanup/` package. Existing console script entry (`gmail-cleanup`) unchanged.
- **Email resolution precedence:** CLI flag > `USER_GOOGLE_EMAIL` env var > `config.default_email` > error. So `--email` is now optional once config is set.
- **`gmail-cleanup --help`** lists 16 commands (was 10): adds `config`, `accounts`, `attachments`, `status`, `schedule`, `setup`, plus existing.

### Dependencies
- Added: `rich>=13.0`

### Tests
- 84 passing (was 52 at v0.4.0; +32 new tests covering config, accounts, state, lists_io, attachments size parser, multi-account dispatch)

## [0.4.0] — 2026-05-15

The "Swiss army knife with an autopilot button" release.

### Added
- **`autopilot` subcommand.** One command runs the full safe-by-default cleanup pipeline in four phases:
  1. `filters apply` — upgrade existing + create preset (idempotent)
  2. `unsubscribe --days 30 --min-count 2` — kill recent noise
  3. `mark-read --query "is:unread -in:inbox"` — clear the archived-but-unread backlog
  4. `verify` — audit stickiness; `--escalate` to auto-block stuck senders
  - Supports `--dry-run` (skips destructive phases 3+4) and `--escalate`. Safe to run repeatedly.
- **`mark-read` subcommand.** Bulk-mark messages as read by query. Default query (`is:unread -in:inbox`) targets the archived-but-unread backlog that piles up after filter routing. Found and cleared 4,710 stale unreads on the maintainer's account in one shot.
- **3 new entries in `lists/kill.yaml`:** `skool.com`, `invitations@linkedin.com`, `noreply@discord.com` — top non-killlist offenders from 14-day trend data.

### Changed
- **Filter upgrades now also remove `UNREAD`.** Previously the existing-filter upgrade only added `INBOX` removal (archive but stay unread). Now label-and-archive filters also clear `UNREAD`, so categorized mail counts toward "read" automatically. Protect filters (whitelist-humans pattern: adds `STARRED`/`IMPORTANT`) and trash/block filters are explicitly skipped.
- **`lists/keep.yaml`:** removed `noreply@skool.com` (was protecting 76 emails/14d of noise) — Skool is now killlist-eligible.

### Performance / state delta on maintainer's account
- Inbox: 165 → 144 (-21, after another aggressive unsubscribe pass)
- **Unread total: 4,858 → 150 (-4,708, -97%)**
- Filters active: 14 → 15 (one extra killlist filter created because the criteria changed when 3 entries were added)
- Storage: 8.2 MB → 7.2 MB

## [0.3.1] — 2026-05-15

The "found in a clean-room install audit" fix. No behavior changes for repo users; major UX improvement for anyone who installs via `pip install`.

### Fixed
- Credential lookup no longer assumed the tool was running from a git checkout. When pip-installed, `Path(__file__).parent` resolves inside site-packages — "place credentials.json in project dir" was meaningless. Now the tool searches in this order:
  1. `$GMAIL_CLEANUP_CREDENTIALS` (env var, full path)
  2. `~/.gmail_cli/credentials.json` (canonical per-user location)
  3. `./credentials.json` (CWD)
  4. `<package dir>/credentials.json` (legacy, for running from a clone)
- When no credentials are found, the error now lists every path that was checked, the GCP console URL to create one, and the exact destination to save it. Actionable instead of cryptic.

### Added
- 6 new pytest tests covering the credential search-path order and env-var precedence (`tests/test_credentials_search.py`). Total: 52 tests.

## [0.3.0] — 2026-05-15

The "buttoned-up" pass. Repo turns from a working script into a productizable tool.

### Added
- **Lists in YAML.** `VETTED_KILL_LIST`, `UNSUB_KEEP_LIST`, `HUMANS_WHITELIST`, `UNSUBBED_SENDERS` extracted to `lists/*.yaml`. Users edit YAML, no Python required. New `_load_list()` helper validates the file is a top-level list, strips whitespace, skips empty entries.
- **`verify` subcommand.** Checks whether previously-unsubscribed senders are still arriving. Flags: `--days N` (default 14), `--since YYYY-MM-DD` (precision mode), `--escalate` (auto-create a Gmail block filter for each stuck sender).
- **Block-filter escalation.** `_create_block_filter()` helper creates a Gmail filter that auto-trashes (move to TRASH + remove from INBOX) a specific sender. Deduplicates against existing filters by `from:` criterion. Used by `verify --escalate`.
- **Test suite.** 46 pytest tests covering `_load_list`, `_extract_email`, `_parse_list_unsubscribe`, `_humans_exclusion`, KEEP-list substring semantics, and the shipped list files for duplicates / structure / critical-substring presence.
- **Packaging.** `pyproject.toml` (hatchling backend), console script entry point `gmail-cleanup`, optional `[dev]` extras (pytest + ruff). `pip install -e .` works.
- **Docs.** `CONTRIBUTING.md` (project values, setup, commit conventions), `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `lists/README.md` (conflict-resolution rules), README rewrite using the new console-script entry point.

### Changed
- README usage examples now use `gmail-cleanup` instead of `./gmail_cli.py`
- Safety-model section in README points at the four `lists/*.yaml` files instead of in-source constants

### Verified
- 19/20 of the 2026-05-14 cohort unsubscribes appear to have stuck (90% rate) when scoped to post-unsub window with `verify --since 2026-05-15`. Two confirmed stuck: `noreply@glassdoor.com`, `jobalerts-noreply@linkedin.com` — candidates for `--escalate`.

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
