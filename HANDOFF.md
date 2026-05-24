# HANDOFF

**Last updated:** 2026-05-24
**Account under test:** bgorzelic@gmail.com
**Tool version:** v0.5.2
**Repo status:** Public — github.com/bgorzelic/gmail-cleanup

## What this is

`gmail-cleanup` — a safety-first CLI for reclaiming a Gmail inbox.
Working prototype + productized OSS tool. See [`README.md`](README.md).

## Current state

- **Inbox:** 47 emails (humans + drafts only)
- **Filters in Gmail:** 34 active (15 prior + 19 new block filters from escalation)
- **Unsubscribed senders to date:** 146 (20 on 2026-05-14 + 25 on Day-2 backfill + 101 on 2026-05-24)
- **Verification debt:** 0 known stuck (all 19 from the 2026-05-14 cohort that didn't stick are now hard-blocked via filters)

## Last session (2026-05-24)

Full autopilot run + aggressive override sweep. Inbox went 570 → 47 (−92%, −26 MB).

- **Autopilot --escalate.** Phase 2 unsubscribed 101 new senders (293 messages archived, 0 failures). Phase 4 discovered **19 of the 20** 2026-05-14 unsubs never actually stuck — block filters auto-created for all of them. Auto-close-the-loop appended the new cohort to `lists/unsubbed.yaml`, committed and pushed.
- **Aggressive override.** Re-applied the 2026-05-14 "keep only obvious humans" pattern: archived all 236 remaining inbox messages except the protected senders list. Marked 213 unread-archived as read.
- **Keep-list update.** Added pyramidci.com humans (`manish.giri`, `yamini1`) to memory `project_correspondence_keep_list.md`. `noreply3@pyramidci.com` is noted as automated → not protected.
- **Memory hygiene.** Updated `project_unsubscribe_log.md` with today's run and the critical lesson: List-Unsubscribe POST 200 OK ≠ actual unsubscribe.

**Commits:** `d5d1c50` data: log 2026-05-24 cleanup — +101 unsubs

## Key insight

**Unsubscribe verification is non-negotiable.** 19/20 (95%) of the 2026-05-14 cohort silently failed despite returning 200 OK on the RFC 8058 POST. The verify+escalate cycle built into autopilot is the only way to actually shut these senders up — first POST, wait 7–14 days, then block-filter anything still arriving.

## Next steps

1. **Schedule daily autopilot** — `gmail-cleanup schedule install --escalate` to run unattended via launchd. Inbox is clean enough that daily maintenance is now realistic.
2. **PyPI publish** — repo is public, v0.5.2 is publish-quality. Reserve `gmail-cleanup` on PyPI and ship `0.5.2` as the first release.
3. **Decisions still open from prior HANDOFF:**
   - `noreply@skool.com` (166 msgs/30d in All Mail, but routed by filter, not in inbox) — keep or kill?
   - `invitations@linkedin.com` — not yet on `lists/kill.yaml`; consider adding.
4. **v0.6 candidates** — partial-unsubscribe reporting (which senders POST'd but kept sending), `--min-count 1` flag for autopilot, optional dry-run summary email.

## Open questions

- Does the user want `lists/unsubbed.yaml` to remain repo-tracked (current behavior — grows with personal cohort, useful as seed for new users) or move under `~/.gmail_cli/` as per-user state?
- Skool decision (see above).

## Blockers

None.

## How to pick up

```bash
cd ~/dev/projects/gmail-cleanup
source .venv/bin/activate
gmail-cleanup --email bgorzelic@gmail.com status
gmail-cleanup --email bgorzelic@gmail.com autopilot --escalate --dry-run
```
