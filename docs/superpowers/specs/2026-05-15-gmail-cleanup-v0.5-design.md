# gmail-cleanup v0.5 — Design

**Status:** Approved (2026-05-15) — pending writing-plans → implementation.
**Author:** Brian Gorzelic, with brainstorming via Claude.
**Tag target:** `v0.5.0` on `main`.
**Baseline:** `v0.4.0` (autopilot, mark-read, filters apply, unsubscribe, verify, kill/keep/humans YAML lists).

---

## 1. Goal

Make gmail-cleanup feel like the "Swiss army knife" of Gmail management: comprehensive feature surface and dramatically easier first-run experience. Single release, layered build, multiple commits per layer, one tag.

**Non-goals for v0.5:**
- Not porting to TypeScript / not building on top of `gws`. Path X (hybrid) — gmail-cleanup stays Python, future suite tools may evaluate `gws` separately. See section 13.
- Not folding into `inbox-detox` SaaS. They stay sibling projects.
- Not building Linux/Windows scheduler support (Mac-only in v0.5; planned v0.6).
- Not adding LLM-based triage (post-v1.0 idea).

## 2. Scope summary

Eight items across four layers:

| Layer | Item | Why this layer |
|---|---|---|
| 1 — Foundation | Config file (`~/.gmail_cli/config.yaml`) | Unlocks multi-account; sets default email so flags become optional |
| 2 — Quick wins | Auto-add successful unsubs to `lists/unsubbed.yaml` | Closes a manual gap, ~10 LOC |
| 2 — Quick wins | Rich progress UI + `--quiet`/`--verbose` modes | Touches every command; foundation for cron-friendly output |
| 3 — Features | Status / dashboard command | Pairs with scheduled autopilot (morning glance) |
| 3 — Features | Storage / attachment cleanup command | Different cleanup angle; addresses 15 GB quota pain |
| 3 — Features | Multi-account batch ops | Builds on Layer 1 (config); high value for users with personal + work |
| 3 — Features | Scheduled autopilot (launchd, Mac-only) | Set-it-and-forget-it; biggest "hands-off" win |
| 4 — Onboarding | OAuth setup wizard | Removes the #1 barrier for non-developer adoption |

## 3. New dependencies

| Package | Version | Used by |
|---|---|---|
| `rich` | `>= 13` | Progress bars, status tables |

**Considered and rejected:** `ruamel.yaml` for comment-preserving YAML round-trips. Rejected because losing comment ordering in auto-managed `unsubbed.yaml` is acceptable when paired with a header comment explaining the file is auto-managed.

## 4. Component design

### 4.1 Config file (`~/.gmail_cli/config.yaml`)

**Schema:**
```yaml
default_email: you@gmail.com
accounts:
  - email: you@gmail.com
    label: personal
  - email: work@company.com
    label: work
lists_dir: ~/.gmail_cli/lists      # optional; defaults to package lists/
defaults:
  unsubscribe: { days: 30, min_count: 2 }
  verify: { days: 14 }
```

**Precedence:** CLI flag > config file value > hard-coded default.
**Backward compatibility:** Missing config → use existing defaults. Every current command keeps working unchanged.

**New commands:**
- `gmail-cleanup config show` — print loaded config + resolved precedence
- `gmail-cleanup config init` — write a starter config file at `~/.gmail_cli/config.yaml`

**Implementation:** Single `_load_config() -> dict` helper, called once at CLI entry. Returns merged dict with defaults filled in. Lookup order similar to credentials search:

1. `$GMAIL_CLEANUP_CONFIG` env var
2. `~/.gmail_cli/config.yaml`
3. `./gmail-cleanup.yaml` (CWD)

### 4.2 Multi-account batch ops

**New flag:** `--all-accounts` on `autopilot`, `stats`, `verify`. Iterates `config.accounts`. **Each account uses its own cached OAuth token** (already supported per-account by `_token_path()`).

**Failure semantics:** A failure in one account does NOT abort the run. Failures are collected and printed at end as a summary. Exit code is the number of failed accounts (0 = all OK).

**New commands:**
- `gmail-cleanup accounts list` — show configured accounts and token status (cached / expired / missing)
- `gmail-cleanup accounts add EMAIL [--label X]` — append to `config.accounts`
- `gmail-cleanup accounts remove EMAIL` — remove from `config.accounts`; optionally delete cached token

### 4.3 Auto-close-the-loop on unsubscribes

**Behavior:** On a successful `_execute_unsubscribe()`, append `sender` to `lists/unsubbed.yaml`. Dedup against existing entries.

**Implementation:** Small `_append_to_unsubbed(senders: Iterable[str]) -> int` helper in the lists module. Loads current file, merges (dedup), writes back. **Loses YAML comment ordering on write** — accepted trade-off. Top-of-file comment header is preserved by reading first N comment lines, dedup'ing the body, writing comments + dedup body back.

**Triggered from:** `cmd_unsubscribe` (after `_execute_unsubscribe` returns `True, method`). Newly-added senders are also surfaced in the command's final summary block.

### 4.4 Storage / attachment cleanup command

**Signature:**
```bash
gmail-cleanup attachments [--over SIZE] [--older-than DAYS] [--archive|--delete] [--dry-run] [--limit N]
```

**Defaults:** `--over 10mb --older-than 180d --dry-run`. Safe-by-default — no destructive action without explicit flag.

**Behavior:** Query Gmail for `has:attachment larger:10M older_than:180d` (translated from CLI flags). Group results by sender, ranked by **total bytes attributed**, not message count. Output:

```
🗂  Attachment cleanup preview
Found 47 emails over 10MB older than 180d, ~2.1 GB total

Rank  Bytes      Sender                              Messages
1     842 MB     receipts@bigvendor.com                    12
2     310 MB     no-reply@ci.example.com                    8
...
```

With `--archive` or `--delete`: applies the action via existing infrastructure. Confirmation prompt unless `--yes`.

### 4.5 Scheduled autopilot

**Mac-only in v0.5.** Linux/Windows print a "not yet supported, planned v0.6" message and exit 1.

**Commands:**
- `gmail-cleanup schedule install [--time HH:MM] [--escalate] [--account EMAIL]` — writes launchd plist
- `gmail-cleanup schedule uninstall` — `launchctl unload` + remove plist
- `gmail-cleanup schedule status` — show next-run time, log location

**Plist details:**
- Path: `~/Library/LaunchAgents/com.github.bgorzelic.gmail-cleanup.plist`
- Default time: **08:00 local** (per Open Design Question 2)
- Command: `gmail-cleanup --email <account> autopilot [--escalate] --quiet`
- StdOut/StdErr: `~/.gmail_cli/logs/autopilot-YYYY-MM-DD.log` (rotated by date stamping)

### 4.6 OAuth setup wizard

**Honest scope:** delegated automation, ~80% friction reduction. Not full automation (requires user clicking through GCP web UI; doesn't shell out to `gcloud`).

**Per Open Design Question 1:** No `gcloud` integration in v0.5. Plain web-based flow only.

**Flow (`gmail-cleanup setup`):**

1. Detect existing `~/.gmail_cli/credentials.json` → prompt to overwrite (default: no)
2. Print intro: "I'll walk you through 4 short steps. Total: ~3 minutes."
3. **Step 1:** Open browser to `console.cloud.google.com/projectcreate`. On-screen text: "Name the project anything, e.g. `gmail-cleanup`. Click Create. Wait ~30 seconds for it to provision. Press Enter when done."
4. **Step 2:** Open browser to the Gmail API library page. On-screen: "Click Enable. Press Enter when done."
5. **Step 3:** Open browser to OAuth client creation. On-screen: "Choose Application type: Desktop app. Name it anything. Click Create. A modal will appear — click 'Download JSON'. Press Enter when downloaded."
6. **Step 4:** Poll `~/Downloads` for new `client_secret_*.json` files (modified in the last 5 minutes). When found, prompt for confirmation, move to `~/.gmail_cli/credentials.json`. Fallback if no match: ask user to enter the path manually.
7. **Step 5:** Trigger an OAuth consent flow as smoke test. On success, print the authenticated email.
8. **Step 6:** Offer to register the authenticated email as `default_email` in `config.yaml` (creating the config file if absent).

**Re-runnability:** Safe to run multiple times. Each step is idempotent (overwrites or skips based on existing state).

### 4.7 Status / dashboard command

**Signature:** `gmail-cleanup status [--account EMAIL]`

**Sample output:**
```
gmail-cleanup status — you@gmail.com

📥 Inbox: 144     📬 Unread: 150    💾 Storage: 7.2 MB
🛡  Filters active: 15 (3 protect, 4 noise-archive, 8 categorize-and-archive)
📋 Lists: 36 kill · 43 keep · 10 humans · 20 unsubbed
🤖 Last autopilot: 2026-05-15 14:30 (today, scheduled)
⚠️  Stuck senders (last 7d): 0
📈 Last 7d: -45 unread · -120 filter-routed · 3 new unsubs
```

**State file:** Per Open Design Question 3 → **per-account** state at `~/.gmail_cli/state_<email>.json`. Schema:
```json
{
  "last_autopilot_at": "2026-05-15T14:30:00Z",
  "last_autopilot_source": "scheduled",
  "history": [
    {"at": "2026-05-15T14:30:00Z", "unread_delta": -45, "routed": 120, "new_unsubs": 3}
  ]
}
```

**Writers:** autopilot, unsubscribe, mark-read each append an event to history.
**Reader:** status command.
**Retention:** keep last 30 entries, prune older.

### 4.8 Rich progress UI

**Library:** `rich.progress.Progress` (existing dep ecosystem standard).

**Pattern:** Wrap inner loops in `search_messages`, `cmd_top_senders`, `cmd_unsubscribe`, `cmd_mark_read`, `cmd_archive`, `cmd_delete`, `cmd_verify`. Existing `\r`-style progress prints removed.

**Modes:**
- Default: full rich output (progress bars, color)
- `--quiet`: no progress, only end-of-run summary. Cron-friendly.
- `--verbose`: extra debug info (search queries, batch sizes, per-account headers in multi-account runs)

**Ctrl-C handling:** `Progress` context manager tears down cleanly; pending operations log "interrupted" and exit non-zero.

## 5. Data flow

**Config-load → command-dispatch → API-call → state-update pipeline:**

```
                  ┌────────────────────┐
  CLI args ──────▶│  Argparse parser   │
                  └────────┬───────────┘
                           │
                  ┌────────▼───────────┐
                  │  _load_config()    │ ← ~/.gmail_cli/config.yaml
                  │  resolve flag prec │
                  └────────┬───────────┘
                           │
              ┌────────────┼─────────────┐
              │            │             │
  --all-accounts loop?    no            yes
              │            │             │
              │            ▼             ▼
              │      cmd_X(args)   for each account in config:
              │            │           cmd_X(args)
              │            │           track success/failure
              │            │             │
              │            ▼             ▼
              │       Gmail API     summary at end
              │            │             │
              │            ▼             │
              │     append state ◀───────┘
              │            │
              └────────────▼
                  exit code = #failed accounts
```

## 6. Error handling principles

| Failure mode | Behavior |
|---|---|
| Missing config file | Use built-in defaults; no error |
| Malformed config YAML | Print path + parse error + exit 1 |
| Per-account failure in `--all-accounts` | Record, continue; exit code = #failed |
| Setup wizard interruption (Ctrl-C, browser close) | Re-runnable safely; idempotent steps |
| Scheduled run failure | Exit non-zero; plist `StandardErrorPath` captures it |
| Rich progress + Ctrl-C | Clean teardown, exit non-zero |
| Auto-add-unsubs YAML write failure | Print warning; main command continues |
| Stale OAuth token in multi-account | Skip that account, record, continue |

## 7. Testing strategy

| Component | Approach | Approx tests |
|---|---|---|
| Config loader + precedence | `tmp_path` fixtures (mirror `tests/test_credentials_search.py` pattern) | 8 |
| Auto-add-unsubs YAML round-trip | tmp_path; verify dedup, comment-header preservation, atomic write | 4 |
| Multi-account dispatch | Mock `GmailCLI.__init__` per account; verify partial-failure semantics + exit code | 4 |
| Status command rendering | Mock Gmail API + state file; assert each output section appears | 3 |
| Storage cleanup query building | Unit tests on `_parse_size()` helper (mb/gb suffixes), `--older-than` translation | 3 |
| Multi-account flag wiring | Verify `--all-accounts` errors cleanly without config | 2 |
| Setup wizard | **Manual + smoke; no unit tests.** Browser opens + filesystem polling are too environment-dependent. | 0 |
| Scheduler | **Manual + smoke; no unit tests.** launchctl integration likewise. | 0 |
| Rich progress | **Manual; no unit tests.** Behavior is visual. | 0 |

**Target:** ~75 tests (currently 52), all green.

## 8. Backward compatibility

- All existing commands work unchanged with no config file
- Existing 52 tests stay green (verified after each layer commits)
- Minor-version bump (0.4 → 0.5) signals new features, no breaking changes
- Existing cached OAuth tokens under `~/.gmail_cli/` continue to work
- `lists/*.yaml` schema unchanged (just gains automatic appends via auto-close-the-loop)

## 9. Implementation order (layered)

1. **Layer 1 — Foundation (commit 1):**
   - Add `_load_config()` + `~/.gmail_cli/config.yaml` schema
   - `cmd_config` (show / init)
   - 8 tests
2. **Layer 2 — Quick wins (commit 2):**
   - Auto-add successful unsubs (~10 LOC + 4 tests)
   - Add `rich` dep + `_progress_bar()` wrapper for the major loops + `--quiet`/`--verbose`
3. **Layer 3 — Features:**
   - **Commit 3a:** Status command + state-file writer integration in autopilot/unsubscribe/mark-read
   - **Commit 3b:** Storage / attachment cleanup command
   - **Commit 3c:** Multi-account `accounts` subcommands + `--all-accounts` flag
   - **Commit 3d:** Scheduler `schedule install/uninstall/status` (Mac-only)
4. **Layer 4 — Onboarding (commit 4):**
   - OAuth setup wizard
5. **Layer 5 — Docs + release (commit 5):**
   - README updates featuring `setup`, `status`, `schedule`, `--all-accounts`
   - CHANGELOG v0.5.0 entry
   - HANDOFF refresh
   - ROADMAP refresh (incl. `gws` note — see section 13)
   - Tag v0.5.0, push

## 10. Open design questions — defaults applied

Per user approval (2026-05-15) — proceeding with these defaults:

1. **Setup wizard `gcloud` integration:** Not in v0.5. Plain web-based delegation only. (Future: add an opt-in `--use-gcloud` path if `gcloud` is detected.)
2. **Default scheduled time:** 08:00 local. (Customizable via `--time HH:MM`.)
3. **Status state file location:** Per-account at `~/.gmail_cli/state_<email>.json` (correct semantics for multi-account; small file count is acceptable).

## 11. Risk register

| Risk | Mitigation |
|---|---|
| `rich` dep adds install weight | Minimal — `rich` is widely used and pure-Python. Accept. |
| Setup wizard misses a credentials.json download | Manual-path-prompt fallback after 60s of polling. |
| Multi-account `--all-accounts` runs slow if one account hangs | Per-command timeout (configurable in `config.defaults`, default 5 min/account). |
| Scheduler conflicts with existing user launchd jobs | Use a clearly-namespaced plist label (`com.github.bgorzelic.gmail-cleanup`). Detect and refuse install if same label exists; offer `--force`. |
| Auto-add-unsubs corrupts `unsubbed.yaml` on crash | Write to `unsubbed.yaml.tmp` first, then atomic rename. |
| Comment-preservation loss in auto-write is more annoying than expected | If user feedback says so, swap to `ruamel.yaml` in v0.6 (minor change). |

## 12. Acceptance criteria

v0.5 is "done" when all the following hold:

- [ ] All 8 designed components ship in `gmail_cli.py` + supporting modules
- [ ] `gmail-cleanup --help` lists: `config`, `accounts`, `setup`, `status`, `attachments`, `schedule`, plus existing commands
- [ ] `gmail-cleanup autopilot --all-accounts` runs on a 2-account config without error
- [ ] `gmail-cleanup setup` walks a fresh user from no GCP project to a working `gmail-cleanup stats` in <5 minutes
- [ ] `gmail-cleanup schedule install` creates a working launchd job that runs at the next 08:00 local
- [ ] `gmail-cleanup status` shows complete dashboard within 2 seconds of invocation
- [ ] Full test suite is green (≥75 tests passing)
- [ ] CHANGELOG, README, HANDOFF, ROADMAP updated
- [ ] Tag `v0.5.0` pushed to GitHub
- [ ] Manual smoke: install in a clean `/tmp/v05-test/.venv`, run `setup`, `autopilot`, `status`, `schedule install`, all succeed

## 13. Suite architecture note (added 2026-05-15)

This v0.5 design **does not** change the suite-architecture decision deferred in `ROADMAP.md`. Decision when starting the next tool (calendar / docs / workspace):

- **Path 1 (Python-native shared core lib):** Build `workspace-utils-core` Python library; each suite tool depends on it.
- **Path 2 (Delegate API access to `gws`):** Future tools shell out to `gws` for Workspace API calls and add workflow on top.

`gws` (`github.com/googleworkspace/cli`) was evaluated and rejected as a v0.5 substrate for gmail-cleanup (would require TS port + heavy install). It remains a candidate for the suite when tool #2 starts. Decision will be made informed by actual use of one of these tools.

## 14. Out of scope (documented for future ideas)

These came up during brainstorming and are explicitly deferred:

- LLM-powered smart triage (BYOK OpenAI/Anthropic for classifying ambiguous emails)
- Conversation thread management (archive/label whole threads)
- Filter analytics (`gmail-cleanup filters analyze` — what each filter caught last 30d)
- Snooze automation (rules like "anything from boss outside work hours")
- Stats-over-time UI (graph of unread/inbox/storage over weeks)
- Export / backup (mbox or json bulk export by query)
- Bash/zsh autocompletion
- Interactive TUI mode
- Linux/Windows scheduler support
- PyPI publish (still pending green-light per ROADMAP)
- Homebrew formula
- GitHub Actions CI (lint + test on push)
