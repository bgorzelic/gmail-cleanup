# gmail-cleanup

A safety-first CLI for reclaiming a Gmail inbox. One-click unsubscribe (RFC 8058), declarative filter management, and a hard-coded KEEP list that physically cannot unsubscribe you from your bank.

## Why

Most Gmail "cleanup" tools either (a) leave the work to you or (b) blast through your inbox with no idea what's a newsletter and what's a credit-card fraud alert. This CLI splits the world into three buckets and treats each differently:

- **Real humans** → starred, marked important, spam-shielded (never touched)
- **Must-keep automation** (banks, healthcare, government, brokerage, security) → KEEP list, physically cannot be unsubscribed by the tool
- **Noise** (newsletters, marketing, job spam) → one-click unsubscribed via RFC 8058 and archived (reversible — still in All Mail)

Everything is auditable. Every action is reversible. The KEEP list overrides any "delete this sender" instruction.

## The one-command flow

```bash
gmail-cleanup --email you@gmail.com autopilot
```

That runs the full safe-by-default pipeline:

1. **Apply filters** — declare your categorization rules to Gmail (idempotent)
2. **Unsubscribe** — find noise senders from the last 30 days, hit their one-click unsub, archive
3. **Mark-read** — clear the archived-but-unread backlog
4. **Verify** — audit yesterday's unsubscribes; flag anything still arriving

Safe to run repeatedly. Add `--dry-run` to preview, or `--escalate` to auto-create block filters for senders that ignored their unsubscribe.

## Individual commands

For when you want surgical control:

| Command | What it does |
|---|---|
| `autopilot` | Full pipeline: filters → unsubscribe → mark-read → verify. The "Swiss army knife" entry point. |
| `stats` | Inbox count, unread, storage, oldest email |
| `top-senders --days N` | Rank senders by volume over the last N days |
| `subscriptions` | Find senders with List-Unsubscribe headers |
| `unsubscribe --days N --min-count K` | Auto-discover noise senders, hit their one-click unsub, archive their inbox messages |
| `mark-read --query Q` | Bulk-mark matching messages as read (default: archived-but-unread backlog) |
| `verify --since YYYY-MM-DD [--escalate]` | Check whether previously-unsubscribed senders are still arriving. Optionally auto-create a Gmail block filter for stuck senders. |
| `filters apply` | Create/upgrade Gmail filters with label + archive + mark-read |
| `filters list` | List existing filters |
| `archive` | Bulk archive by sender / category / label / query / age |
| `delete` | Move to trash by same criteria |
| `label` | Create and apply labels |

All destructive commands prompt for confirmation unless you pass `--yes`. `autopilot`, `unsubscribe`, and `filters apply` all support `--dry-run`.

## Install

Requires Python 3.11+ and a GCP project with the Gmail API enabled.

```bash
git clone <this-repo>
cd gmail-cleanup
python3 -m venv .venv
source .venv/bin/activate
pip install -e .          # installs the `gmail-cleanup` console script
# or for dev work (with pytest + ruff):
pip install -e ".[dev]"
```

OAuth setup:

1. Create an OAuth 2.0 Desktop App credential in [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Download the JSON, save it as `credentials.json` in the repo root (see `credentials.example.json` for shape)
3. On first run, a browser window opens for consent. Token cache lands in `~/.gmail_cli/` (per-account, gitignored)

Required OAuth scopes:

- `gmail.modify` — archive, label, modify messages
- `gmail.readonly` — read message headers/metadata
- `gmail.labels` — manage labels
- `gmail.send` — send mailto-style unsubscribe emails
- `gmail.settings.basic` — manage Gmail filters

## Quick start

```bash
# See what's there
gmail-cleanup --email you@gmail.com stats
gmail-cleanup --email you@gmail.com top-senders --days 14

# Preview the autopilot
gmail-cleanup --email you@gmail.com autopilot --dry-run

# Run it
gmail-cleanup --email you@gmail.com autopilot

# Two weeks later — re-run autopilot, with escalation for any stuck senders
gmail-cleanup --email you@gmail.com autopilot --escalate
```

For surgical control, the individual subcommands (above) all work standalone. Autopilot is just a convenience composition.

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
pytest                # run the test suite (46 tests, ~0.1s)
ruff check .          # lint
ruff format .         # format
```

## Project state

See [`CHANGELOG.md`](CHANGELOG.md) for version history and [`HANDOFF.md`](HANDOFF.md) for the current open work. Direction and the path to v1.0 live in [`ROADMAP.md`](ROADMAP.md).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Bug reports and PRs welcome.

## License

MIT — see [`LICENSE`](LICENSE).
