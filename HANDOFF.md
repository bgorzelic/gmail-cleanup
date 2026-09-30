# HANDOFF

**Last updated:** 2026-09-30
**Account under test:** bgorzelic@gmail.com
**Tool version:** v0.6.1 — on PyPI as [`gmail-inbox-cleanup`](https://pypi.org/project/gmail-inbox-cleanup/)
**Repo status:** Public — github.com/bgorzelic/gmail-cleanup

## What this is

`gmail-cleanup` — a safety-first CLI for reclaiming a Gmail inbox.
Install: `pipx install gmail-inbox-cleanup` (the command is `gmail-cleanup`). See [`README.md`](README.md).

## Current state

- **Inbox:** 520 conversations, 328 unread (was 3,933 / 3,516 at the start of 2026-09-30)
- **Filters in Gmail:** 31 active
- **Unsubscribed senders on record:** 352 (`~/.gmail_cli/lists/unsubbed.yaml`) — 121 legacy entries without timestamps + 231 added 2026-09-30 with `unsubscribed_at`
- **Verification:** 114 silent, 231 pending (inside the 2-day grace period), 7 stuck — no block filters created yet
- **Personal state lives in `~/.gmail_cli/`**, not the repo: lists, OAuth client, token, `backups/`

## Last session (2026-09-30)

Shipped v0.6.0 and v0.6.1 and cleaned the inbox with them.

**Release**
- First PyPI release, renamed to `gmail-inbox-cleanup` (`gmail-cleanup` on PyPI is an unrelated abandoned package).
- PR #3 merged to `main`; tag `v0.6.0`; GitHub Release triggers `.github/workflows/publish.yml` (PyPI trusted publishing, environment `pypi`). Verified by installing from PyPI into a clean venv.
- Also pushed 20 September commits that had only existed locally.
- **v0.6.1** (same day): an exhausted Gmail quota (`dailyLimitExceeded` / `quotaExceeded`) now stops the run with exit code 2 instead of being retried.
- After-action report: [`docs/AAR-2026-09-30.md`](docs/AAR-2026-09-30.md).

**Code (all in CHANGELOG 0.6.0)**
- Lists split: packaged seeds in `gmail_cleanup/lists/` (only `keep.yaml` populated) merged with `~/.gmail_cli/lists/`. The tool never writes into the installed package.
- `verify` only counts mail after `unsubscribed_at` + 2 days; pending senders are never escalated.
- Humans always win in `unsubscribe` (this was documented but never enforced).
- Removed the `has:list` catch-all filter — not a real Gmail operator, it matched nothing.
- `filters apply` replaces a grown list's filter instead of stacking; skips empty lists.
- Header scans batched (25 per request) and paced to Gmail's documented quota; `Retry-After` backoff; throttle remembered in `~/.gmail_cli/rate_limit_<email>.json`.
- `status` matches Gmail's UI from one API call.
- `autopilot --days / --min-count / --email-summary`, `verify --grace-days`.
- Tests 185 → 221; `HOME` is sandboxed for the whole test session.

**Inbox (three live runs + one manual scrub)**
- Autopilot, last 30 days: 163 unsubscribed, 1,021 archived.
- `unsubscribe --days 125` (whole inbox): 191 unsubscribed, 1,105 archived.
- Manual category scrub: archived 408 Promotions, 159 Social, 810 Updates older than 14 days. Undo manifest: `~/.gmail_cli/backups/archived-by-category-20260930-024043.json`.
- Final autopilot on the released code: 1 unsubscribed; replaced two older unsubscribed-sender filters (20 and 121 senders) with one covering all.
- Deleted the broken `has:list` filter (backup in `~/.gmail_cli/backups/`). Nothing was deleted from mail — archive only.
- Added 9 personal keep entries (`~/.gmail_cli/lists/keep.yaml`) for account, finance and health senders the seed list missed.

**Sister project — Inbox Detox** (`~/dev/projects/inbox-detox`, private)
- It had the same outdated quota numbers. Fix is open as inbox-detox PR #2 (not merged, not deployed), with a cross-project analysis in its `docs/GMAIL_CLEANUP_SYNERGY.md`.
- Shared direction: one Gmail engine instead of two; incremental sync via `history.list` for both.

## Key insights

- **The May "19 of 20 unsubscribes failed" finding was probably inflated.** `verify` then counted mail sent *before* the unsubscribe. Some of those 19 block filters may be for senders that did stop.
- **Gmail's real quota is tighter than commonly cited**: 6,000 units/min per user and `messages.get` = 20 units (not 5). Even at exactly that rate, 50-wide batches were throttled; 25-wide are not much. Google plans to bill overage later in 2026.
- **Gmail filters cannot detect newsletters.** Only reading `List-Unsubscribe` headers can.

## Next steps

1. **Run `gmail-cleanup verify` on or after 2026-10-02** — 231 senders leave the grace period. Review the stuck list, then `verify --escalate` if it looks right. Currently stuck: LinkedIn (messages-noreply, notifications-noreply), Fox Nation, Wingstop, Mobbin, make.co, IMDb.
2. **Schedule daily autopilot** — `gmail-cleanup schedule install --escalate` is now safe (grace period), but do step 1 by hand once first.
3. **Decide on inbox-detox PR #2** — correct quota costs make its whole-inbox scan too slow for one serverless request; pick a scan design before deploying.
4. **v0.7: incremental sync** via `history.list` so daily runs fetch only new mail (see ROADMAP "v0.7 candidates" for the full list: timestamp legacy entries on re-unsubscribe, chunk the big `from:` filter, a `scrub` command, make `stats` match `status`, seed keep-list additions).
5. **README comparison table** — add `Gururagavendra/gmail-cleaner`, `justlinuxnoob/hush`, `elie222/inbox-zero` (AGPL — ideas only).

## Open questions

- `noreply@skool.com` and `invitations@linkedin.com` are on the personal kill list; still the right call?
- The personal `humans` / `unsubbed` lists remain in the public git history (pre-0.6 commits). Rewrite history, or accept?
- 11 stale agent worktrees under `.worktrees/` — remove?

## Key files

- `gmail_cleanup/__init__.py` — CLI, `GmailCLI`, all commands; quota constants and `get_messages_metadata` (batched fetch) near the top
- `gmail_cleanup/lists_io.py` — seed + user `unsubbed.yaml` read/append
- `gmail_cleanup/lists/` — packaged seeds (only `keep.yaml` populated)
- `tests/test_safety.py`, `tests/test_verify_window.py`, `tests/test_api_usage.py` — the safety, verify and quota guarantees
- `ARCHITECTURE.md` — six safety invariants and the Gmail API quota rules
- `.github/workflows/publish.yml` — PyPI release on GitHub Release

## Blockers

None.

## How to pick up

```bash
cd ~/dev/projects/gmail-cleanup
source .venv/bin/activate
gmail-cleanup --email bgorzelic@gmail.com status
gmail-cleanup --email bgorzelic@gmail.com verify          # after 2026-10-02
gmail-cleanup --email bgorzelic@gmail.com autopilot --dry-run
```
