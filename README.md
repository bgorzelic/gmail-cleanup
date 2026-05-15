# gmail-cleanup

A safety-first CLI for reclaiming a Gmail inbox. One-click unsubscribe (RFC 8058), declarative filter management, and category sweeps — without the risk of accidentally archiving a bank alert.

## Why

Most Gmail "cleanup" tools either (a) leave the work to you or (b) blast through your inbox with no idea what's a newsletter and what's a credit-card fraud alert. This CLI splits the world into three buckets and treats each differently:

- **Real humans** → starred, marked important, spam-shielded (never touched)
- **Must-keep automation** (banks, healthcare, government, brokerage, security) → hard-coded KEEP list, physically cannot be unsubscribed by the tool
- **Noise** (newsletters, marketing, job spam) → one-click unsubscribed via RFC 8058 and archived (reversible — still in All Mail)

Everything is auditable. Every action is reversible. The KEEP list overrides any "delete this sender" instruction.

## What it can do

| Command | What it does |
|---|---|
| `stats` | Inbox count, unread, storage, oldest email |
| `top-senders --days N` | Rank senders by volume over the last N days |
| `subscriptions` | Find senders with List-Unsubscribe headers |
| `unsubscribe --days N --min-count K` | Auto-discover noise senders, hit their one-click unsub, archive their inbox messages |
| `filters apply` | Create/upgrade Gmail filters with archive action |
| `filters list` | List existing filters |
| `archive` | Bulk archive by sender / category / label / query / age |
| `delete` | Move to trash by same criteria |
| `label` | Create and apply labels |

All destructive commands prompt for confirmation unless you pass `--yes`. `unsubscribe` and `filters apply` both support `--dry-run`.

## Install

Requires Python 3.11+ and a GCP project with the Gmail API enabled.

```bash
git clone <this-repo>
cd gmail-cleanup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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
# What's the damage?
./gmail_cli.py --email you@gmail.com stats
./gmail_cli.py --email you@gmail.com top-senders --days 14 --count 30

# Preview a cleanup pass
./gmail_cli.py --email you@gmail.com unsubscribe --days 30 --min-count 3 --dry-run

# Pull the trigger
./gmail_cli.py --email you@gmail.com unsubscribe --days 30 --min-count 3

# Set up declarative filters so this doesn't happen again
./gmail_cli.py --email you@gmail.com filters apply --dry-run
./gmail_cli.py --email you@gmail.com filters apply
```

## Safety model

Three hard-coded lists in `gmail_cli.py` govern behavior:

- **`UNSUB_KEEP_LIST`** — substring matches against the sender; if matched, the unsubscribe is refused. Covers banks, healthcare, government (.gov), brokerages, security/account-protection senders. False positives are intentional — better to miss an unsub than to silently kill a fraud alert.
- **`HUMANS_WHITELIST`** — real correspondents. They are explicitly excluded from `has:list` catch-all filters and get a protective treatment (star + important + spam-protect) when the filter preset is applied.
- **`VETTED_KILL_LIST`** — known noise domains, kept in code for traceability. Killlist matches override the auto-discovery threshold.

The unsubscribe flow prefers RFC 8058 one-click POST (the standard Gmail/Apple now require for bulk senders). Falls back to GET, then mailto. Senders without any `List-Unsubscribe` header are skipped, not silently archived — that's a guard against accidentally archiving a real person.

## Project state

See [`CHANGELOG.md`](CHANGELOG.md) for the 2-day cleanup campaign that produced this tool, and [`HANDOFF.md`](HANDOFF.md) for current state.

## Roadmap

This is the working prototype for a productized email-management toolset. Direction notes in [`ROADMAP.md`](ROADMAP.md).

## License

TBD — currently a personal/internal tool. License decision pending productization direction.
