# HANDOFF

**Last updated:** 2026-05-15
**Account under test:** bgorzelic@gmail.com
**Tool version:** v0.5.0

## What this is

`gmail-cleanup` — a safety-first CLI for reclaiming a Gmail inbox. Working prototype for a productized email-management toolset. See [`README.md`](README.md).

## Current state

- **Inbox:** 147 emails (down from 7,283 at campaign start on 2026-04-28)
- **Filters in Gmail:** 12 active, all archiving (8 upgraded from label-only + 4 new preset filters)
- **Unsubscribed senders to date:** 45 (20 on Day 1 + 25 on Day 2)
- **Verification debt:** 3 Day-1 unsubscribes failed to stick (localflirt, jobalerts-noreply@linkedin.com, astro@forwardfuture.ai) → still arriving as of 2026-05-15

## Last session (2026-05-15, v0.5.0 — the "Swiss army knife" release)

v0.5.0 shipped eight new components across four layers:

- **Config foundation.** `~/.gmail_cli/config.yaml` with deep-merge defaults and env-var override. `config show / init` subcommands. Email resolution precedence: CLI flag > `USER_GOOGLE_EMAIL` > config default > error — `--email` is now optional once configured.
- **Multi-account support.** `accounts list / add / remove`. `--all-accounts` flag on `autopilot`, `stats`, `verify` with partial-failure semantics.
- **Auto-close-the-loop.** Successful unsubs auto-append to `lists/unsubbed.yaml` via atomic-write helper.
- **`attachments` subcommand.** Finds oversized old emails, ranks senders by bytes, supports `--archive` / `--delete` with confirmation.
- **`status` dashboard.** Live Gmail counts, filter inventory, list sizes, 7-day history — all in one view.
- **`schedule` subcommand.** Daily launchd autopilot on macOS (`install / uninstall / status`).
- **`setup` wizard.** 6-step interactive flow: GCP browser open → credentials poll → OAuth smoke test → account registration. Reduces first-run friction by ~80%.
- **Rich progress UI + global flags.** `--quiet` (cron-safe) and `--verbose` (debug) wired through all commands.
- **Per-account state file.** `~/.gmail_cli/state_<email>.json` with 30-entry history cap.
- **Package layout.** `gmail_cli.py` → `gmail_cleanup/` package. Console script entry unchanged.
- **Test suite:** 84 passing (up from 52 at v0.4.0; +32 new tests).

## Next steps

1. **Escalate the 2 confirmed-stuck senders.** Run `gmail-cleanup --email bgorzelic@gmail.com verify --since 2026-05-15 --escalate` to auto-create block filters for `noreply@glassdoor.com` and `jobalerts-noreply@linkedin.com`.
2. **Manual step at source:** visit [github.com/settings/notifications](https://github.com/settings/notifications) and disable email notifications for repos you don't actively maintain. The filter routes GitHub mail out of inbox, but the only way to stop generation is at the source.
3. **Skool decision:** noreply@skool.com is on `lists/keep.yaml` but produced 76 emails in 14 days. If not actively used, remove from keep.yaml.
4. **LinkedIn invitations:** invitations@linkedin.com (13/14d) isn't in `lists/kill.yaml` yet — consider adding.
5. **Push to public GitHub** when ready — current state is publish-quality, just needs the remote.

## Productization direction (decided 2026-05-15)

**Standalone OSS CLI.** This repo stays focused — no umbrella suite, no folding into `inbox-detox`. Ship to public GitHub when ready, eventually publish to PyPI as `gmail-cleanup`. License: MIT. **All v1.0 polish items are now done.**

**Path X (hybrid) note.** `gmail-cleanup` stays Python — mature Google API client, no reason to switch. If the suite expands to tool #2 (Calendar, Drive, etc.), `github.com/googleworkspace/cli` (`gws`) is a candidate for the Go-based API layer. Decision deferred until there's a concrete second tool to evaluate it against.

## Open questions

- Ready for public GitHub. Awaiting your call on when to flip the remote on.

## Blockers

None. Everything is reversible. The 3 failed unsubscribes are tolerable until the next verification window.

## How to pick up

```bash
cd ~/dev/projects/gmail-cleanup
source .venv/bin/activate
gmail-cleanup stats
gmail-cleanup status
gmail-cleanup autopilot --dry-run
```
