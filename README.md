# gmail-cleanup

A safety-first CLI for reclaiming a Gmail inbox. One-click unsubscribe (RFC 8058), declarative filter management, and a hard-coded KEEP list that physically cannot unsubscribe you from your bank.

## Why

Most Gmail "cleanup" tools either (a) leave the work to you or (b) blast through your inbox with no idea what's a newsletter and what's a credit-card fraud alert. This CLI splits the world into three buckets and treats each differently:

- **Real humans** → starred, marked important, spam-shielded (never touched)
- **Must-keep automation** (banks, healthcare, government, brokerage, security) → KEEP list, physically cannot be unsubscribed by the tool
- **Noise** (newsletters, marketing, job spam) → one-click unsubscribed via RFC 8058 and archived (reversible — still in All Mail)

Everything is auditable. Every action is reversible. The KEEP list overrides any "delete this sender" instruction.

## The one-command flow

**New to the tool?** Run the setup wizard first — it handles GCP credentials, OAuth, and account registration in six steps:

```bash
gmail-cleanup setup
```

Then run autopilot daily (once config is set, `--email` is optional):

```bash
gmail-cleanup autopilot
```

That runs the full safe-by-default pipeline:

1. **Apply filters** — declare your categorization rules to Gmail (idempotent)
2. **Unsubscribe** — find noise senders from the last 30 days, hit their one-click unsub, archive
3. **Mark-read** — clear the archived-but-unread backlog
4. **Verify** — audit yesterday's unsubscribes; flag anything still arriving

Safe to run repeatedly. Add `--dry-run` to preview, or `--escalate` to auto-create block filters for senders that ignored their unsubscribe. Use `--quiet` for cron-friendly silent output, `--verbose` for debug detail.

## Individual commands

For when you want surgical control:

| Command | What it does |
|---|---|
| `setup` | Interactive 6-step wizard: GCP credentials → OAuth → account registration. Start here for new installs. |
| `autopilot` | Full pipeline: filters → unsubscribe → mark-read → verify. The daily driver. |
| `status` | Dashboard: live Gmail counts, filter inventory, list sizes, 7-day history. |
| `stats` | Inbox count, unread, storage, oldest email |
| `top-senders --days N` | Rank senders by volume over the last N days |
| `subscriptions` | Find senders with List-Unsubscribe headers |
| `unsubscribe --days N --min-count K` | Auto-discover noise senders, hit their one-click unsub, archive their inbox messages |
| `mark-read --query Q` | Bulk-mark matching messages as read (default: archived-but-unread backlog) |
| `verify --since YYYY-MM-DD [--escalate]` | Check whether previously-unsubscribed senders are still arriving. Optionally auto-create a Gmail block filter for stuck senders. |
| `attachments [--archive\|--delete]` | Find oversized old emails, rank senders by bytes attributed, reclaim storage. |
| `filters apply` | Create/upgrade Gmail filters with label + archive + mark-read |
| `filters list` | List existing filters |
| `config show` | Print resolved config (merged defaults + env vars + `~/.gmail_cli/config.yaml`). |
| `config init` | Write a starter `~/.gmail_cli/config.yaml`. |
| `accounts list / add / remove` | Manage configured Gmail accounts. |
| `schedule install / uninstall / status` | Set up daily launchd-scheduled autopilot (macOS). |
| `archive` | Bulk archive by sender / category / label / query / age |
| `delete` | Move to trash by same criteria |
| `label` | Create and apply labels |

All destructive commands prompt for confirmation unless you pass `--yes`. `autopilot`, `unsubscribe`, and `filters apply` all support `--dry-run`. Global flags: `--quiet` (cron-safe), `--verbose` (debug).

## Install

Requires Python 3.11+ and a GCP project with the Gmail API enabled.

**Recommended (end users) — isolated install via pipx:**

```bash
pipx install git+https://github.com/bgorzelic/gmail-cleanup.git
```

**For dev work (you want to hack on it):**

```bash
git clone https://github.com/bgorzelic/gmail-cleanup.git
cd gmail-cleanup
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"   # adds pytest + ruff
```

> **Hitting OAuth errors?** See [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) — it covers the consent-screen / test-user step that catches everyone the first time. The `gmail-cleanup setup` wizard handles this for you (v0.5.1+).

OAuth setup (automated — recommended):

```bash
gmail-cleanup setup
```

OAuth setup (manual):

1. Create an OAuth 2.0 Desktop App credential in [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Save the downloaded JSON as `~/.gmail_cli/credentials.json` (or set `$GMAIL_CLEANUP_CREDENTIALS` to its path)
3. On first run, a browser window opens for consent. Token cache lands in `~/.gmail_cli/` (per-account, gitignored)

Required OAuth scopes:

- `gmail.modify` — archive, label, modify messages
- `gmail.readonly` — read message headers/metadata
- `gmail.labels` — manage labels
- `gmail.send` — send mailto-style unsubscribe emails
- `gmail.settings.basic` — manage Gmail filters

## Quick start

**First time?** Run the wizard:

```bash
gmail-cleanup setup
```

It opens the GCP console, waits for you to download `credentials.json`, runs an OAuth smoke test, and registers your account in `~/.gmail_cli/config.yaml`. After that, `--email` is optional everywhere.

**Daily use:**

```bash
# Full pipeline — safe to run repeatedly
gmail-cleanup autopilot

# Preview before committing
gmail-cleanup autopilot --dry-run

# Dashboard — current state at a glance
gmail-cleanup status

# Two weeks later — escalate any stuck senders to block filters
gmail-cleanup autopilot --escalate
```

For surgical control, the individual subcommands (above) all work standalone. Autopilot is just a convenience composition.

## Multi-account

Add and manage multiple Gmail accounts via the `accounts` subcommand:

```bash
gmail-cleanup accounts add work@company.com
gmail-cleanup accounts add personal@gmail.com
gmail-cleanup accounts list
```

Once accounts are registered, run any of these commands across all of them in one shot:

```bash
gmail-cleanup autopilot --all-accounts
gmail-cleanup stats --all-accounts
gmail-cleanup verify --all-accounts
```

Partial-failure semantics: if one account errors, the others still run. Failures are reported at the end.

## Safety model

Four YAML files in [`lists/`](lists/) govern behavior. Edit them to tune the tool — no Python required.

| File | Used by | Match | Behavior |
|---|---|---|---|
| [`lists/keep.yaml`](lists/keep.yaml) | `unsubscribe` | Substring | If sender matches, the unsubscribe is **refused**. Banks, healthcare, .gov, security senders. |
| [`lists/kill.yaml`](lists/kill.yaml) | `unsubscribe`, `filters apply` | Substring | Forces unsubscribe + archive regardless of message-count threshold. |
| [`lists/humans.yaml`](lists/humans.yaml) | `filters apply` | Exact email | Star + mark important + spam-protect. Excluded from `has:list` catch-all. |
| [`lists/unsubbed.yaml`](lists/unsubbed.yaml) | `filters apply`, `verify` | Exact email | Anti-resurrection — if a previously-unsubscribed sender tries to come back, route to archive. `verify` audits this list. |

The unsubscribe flow prefers RFC 8058 one-click POST (the standard Gmail/Apple now require for bulk senders). Falls back to GET, then mailto. Senders without any `List-Unsubscribe` header are skipped, not silently archived — that's a guard against accidentally archiving a real person.

See [`lists/README.md`](lists/README.md) for the conflict-resolution rules between the four files.

## Development

```bash
pip install -e ".[dev]"
pytest                # run the test suite (84 tests, ~0.1s)
ruff check .          # lint
ruff format .         # format
```

## Project state

See [`CHANGELOG.md`](CHANGELOG.md) for version history and [`HANDOFF.md`](HANDOFF.md) for the current open work. Direction and the path to v1.0 live in [`ROADMAP.md`](ROADMAP.md).

## Troubleshooting

Common first-run issues (OAuth consent, missing credentials, token expiry) are covered in [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Bug reports and PRs welcome.

## License

MIT — see [`LICENSE`](LICENSE).
