# HANDOFF

**Last updated:** 2026-05-15
**Account under test:** bgorzelic@gmail.com
**Tool version:** 0.2.0

## What this is

`gmail-cleanup` — a safety-first CLI for reclaiming a Gmail inbox. Working prototype for a productized email-management toolset. See [`README.md`](README.md).

## Current state

- **Inbox:** 147 emails (down from 7,283 at campaign start on 2026-04-28)
- **Filters in Gmail:** 12 active, all archiving (8 upgraded from label-only + 4 new preset filters)
- **Unsubscribed senders to date:** 45 (20 on Day 1 + 25 on Day 2)
- **Verification debt:** 3 Day-1 unsubscribes failed to stick (localflirt, jobalerts-noreply@linkedin.com, astro@forwardfuture.ai) → still arriving as of 2026-05-15

## Last session (2026-05-15)

- Re-authenticated OAuth with broader scopes (added `gmail.settings.basic` and `gmail.send`)
- Built and applied the filter preset via `filters apply`
- Cleared 83 GitHub messages from inbox + routed future GitHub mail to its label automatically
- Ran a second aggressive unsubscribe pass (`unsubscribe --days 30 --min-count 3`) → 25 newly unsubscribed, 61 inbox messages cleared
- Initialized git, wrote `README.md`, `CHANGELOG.md`, `.gitignore`, `credentials.example.json`

## Next steps

1. **Verification recheck (2026-05-29):** rerun `top-senders --days 14 --count 50` and cross-check against the full unsubscribe log. Any of the 45 senders still arriving = unsubscribe failed → escalate (Gmail block filter or report-as-spam).
2. **Manual step at source:** visit [github.com/settings/notifications](https://github.com/settings/notifications) and disable email notifications for repos you don't actively maintain. The filter routes GitHub mail out of inbox, but the only way to stop generation is at the source.
3. **Skool decision:** noreply@skool.com is on the current `UNSUB_KEEP_LIST` but produced 76 emails in 14 days. If you don't actively need them, remove from KEEP and let the killlist take it.
4. **LinkedIn invitations:** invitations@linkedin.com (13/14d) isn't on the killlist yet — consider adding.
5. **Productization decision:** see open question below.

## Open questions

- **Productization direction.** This repo is the working prototype. The separate `inbox-detox` project is the SaaS. Options:
  - (a) Keep this as a standalone open-source CLI (e.g., `gmail-cleanup` or rename to a suite name like `email-utilities`), inbox-detox uses the same core
  - (b) Fold this into inbox-detox as its CLI module
  - (c) Both — extract a shared core library

## Blockers

None. Everything is reversible. The 3 failed unsubscribes are tolerable until the next verification window.

## How to pick up

```bash
cd ~/dev/projects/gmail-cleanup
source .venv/bin/activate
./gmail_cli.py --email bgorzelic@gmail.com stats
./gmail_cli.py --email bgorzelic@gmail.com filters list
```
