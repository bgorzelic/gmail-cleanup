# HANDOFF

**Last updated:** 2026-05-15
**Account under test:** bgorzelic@gmail.com
**Tool version:** 0.3.0

## What this is

`gmail-cleanup` — a safety-first CLI for reclaiming a Gmail inbox. Working prototype for a productized email-management toolset. See [`README.md`](README.md).

## Current state

- **Inbox:** 147 emails (down from 7,283 at campaign start on 2026-04-28)
- **Filters in Gmail:** 12 active, all archiving (8 upgraded from label-only + 4 new preset filters)
- **Unsubscribed senders to date:** 45 (20 on Day 1 + 25 on Day 2)
- **Verification debt:** 3 Day-1 unsubscribes failed to stick (localflirt, jobalerts-noreply@linkedin.com, astro@forwardfuture.ai) → still arriving as of 2026-05-15

## Last session (2026-05-15, v0.3.0 — the "buttoned-up" pass)

- Extracted the four safety lists from `gmail_cli.py` to `lists/*.yaml`. Users now tune the tool by editing YAML, no Python required.
- Added pytest suite — 46 tests, all green. Covers the list loader, header parsers, and KEEP-list substring semantics. Locked in `_is_protected` behavior for banks, .gov, healthcare, security senders.
- Added `verify` subcommand with `--since`, `--escalate`, and the `_create_block_filter` helper. Live-verified the 2026-05-14 unsub cohort: 18/20 stuck (90%), 2 confirmed stuck.
- Packaged with `pyproject.toml` (hatchling) — `pip install -e .` installs the `gmail-cleanup` console script.
- Added `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `lists/README.md`. Rewrote README to use the new console-script entry point.
- Tagged v0.3.0.

## Next steps

1. **Escalate the 2 confirmed-stuck senders.** Run `gmail-cleanup --email bgorzelic@gmail.com verify --since 2026-05-15 --escalate` to auto-create block filters for `noreply@glassdoor.com` and `jobalerts-noreply@linkedin.com`.
2. **Manual step at source:** visit [github.com/settings/notifications](https://github.com/settings/notifications) and disable email notifications for repos you don't actively maintain. The filter routes GitHub mail out of inbox, but the only way to stop generation is at the source.
3. **Skool decision:** noreply@skool.com is on `lists/keep.yaml` but produced 76 emails in 14 days. If not actively used, remove from keep.yaml.
4. **LinkedIn invitations:** invitations@linkedin.com (13/14d) isn't in `lists/kill.yaml` yet — consider adding.
5. **Push to public GitHub** when ready — current state is publish-quality, just needs the remote.

## Productization direction (decided 2026-05-15)

**Standalone OSS CLI.** This repo stays focused — no umbrella suite, no folding into `inbox-detox`. Ship to public GitHub when ready, eventually publish to PyPI as `gmail-cleanup`. License: MIT. **All v1.0 polish items are now done.**

## Open questions

- Ready for public GitHub. Awaiting your call on when to flip the remote on.

## Blockers

None. Everything is reversible. The 3 failed unsubscribes are tolerable until the next verification window.

## How to pick up

```bash
cd ~/dev/projects/gmail-cleanup
source .venv/bin/activate
./gmail_cli.py --email bgorzelic@gmail.com stats
./gmail_cli.py --email bgorzelic@gmail.com filters list
```
