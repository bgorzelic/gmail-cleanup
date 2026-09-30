# gmail-cleanup

[![tests](https://github.com/bgorzelic/gmail-cleanup/actions/workflows/test.yml/badge.svg)](https://github.com/bgorzelic/gmail-cleanup/actions/workflows/test.yml)
[![release](https://img.shields.io/github/v/release/bgorzelic/gmail-cleanup)](https://github.com/bgorzelic/gmail-cleanup/releases)
[![pypi](https://img.shields.io/pypi/v/gmail-inbox-cleanup)](https://pypi.org/project/gmail-inbox-cleanup/)
[![python](https://img.shields.io/badge/python-3.11%20|%203.12%20|%203.13-blue)](https://www.python.org/)
[![license](https://img.shields.io/github/license/bgorzelic/gmail-cleanup)](LICENSE)

**Reclaim your Gmail inbox — safely.** One-click unsubscribe (RFC 8058), declarative filter management, scheduled autopilot, and a hard-coded KEEP list that **physically cannot unsubscribe you from your bank**.

```
$ gmail-cleanup autopilot

🤖 gmail-cleanup autopilot — full inbox cleanup
━━━ Phase 1/4: Apply Gmail filters ━━━
   ✅ 8 upgraded, 4 created (all archive + mark read)
━━━ Phase 2/4: Unsubscribe noise senders (last 30d, min-count 2) ━━━
   ✅ 25 unsubscribed via RFC 8058 one-click POST, 61 inbox messages archived
━━━ Phase 3/4: Mark archived-unread as read ━━━
   ✅ 4,710 messages marked read
━━━ Phase 4/4: Verify previously-unsubscribed senders ━━━
   ⚠️  2 stuck (re-run with --escalate to auto-block)
   ✅ 18 silent (unsubs stuck)

🎉 Autopilot complete. Inbox: 144 (was 7,283) · Unread: 150 (was 4,858)
```

---

## ✨ Why it's different

| | Other tools | gmail-cleanup |
|---|---|---|
| **Safety** | Best-effort | **KEEP list refuses to unsub from banks, .gov, healthcare** |
| **Unsubscribe** | Click the link in the email | **RFC 8058 one-click POST** — the modern standard |
| **Real humans** | At risk of getting archived | **Whitelist-protected** — starred, important, spam-shielded |
| **Reversibility** | Often destructive | **Archive over delete** by default — recoverable from All Mail |
| **Auditability** | Black box | **84-test safety net** + structured logs + state file |
| **Automation** | Manual, daily | **One-command autopilot**, optional daily scheduler (macOS) |

---

## 📦 Installation

**End users — isolated install via [pipx](https://pipx.pypa.io/) (recommended):**

```bash
pipx install gmail-inbox-cleanup
```

The PyPI package is `gmail-inbox-cleanup` (the `gmail-cleanup` name on PyPI belongs to an unrelated project); the command it installs is `gmail-cleanup`.

**Developers — clone and edit:**

```bash
git clone https://github.com/bgorzelic/gmail-cleanup.git
cd gmail-cleanup
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Requirements:** Python 3.11+ and a Google Cloud project with the Gmail API enabled (the setup wizard walks you through both).

> 💡 **Hitting OAuth errors?** See [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md). The most common gotcha (consent screen / test users for unverified apps) is handled by the setup wizard in v0.5.1+.

---

## 🚀 Quick start

```bash
# First time — interactive wizard handles GCP, OAuth, config in 7 steps:
gmail-cleanup setup

# Daily use — one command runs the full cleanup pipeline:
gmail-cleanup autopilot

# Glance at inbox health:
gmail-cleanup status

# Two weeks later — escalate any unsubs that didn't stick:
gmail-cleanup autopilot --escalate
```

`--dry-run` previews any destructive command. `--quiet` for cron-friendly silent runs. `--verbose` for debug.

---

## 🧠 How it works

Every sender falls into one of three buckets:

```
                ┌──────────────────────────────────┐
  inbox mail ──▶│ Real human (humans.yaml)         │──▶  ⭐ star + important + spam-shield
                ├──────────────────────────────────┤
                │ Must-keep automation (keep.yaml) │──▶  🔒 NEVER unsubscribe (safety rail)
                │  banks, .gov, health, brokerage  │
                ├──────────────────────────────────┤
                │ Noise (kill.yaml + auto-discover)│──▶  🗑  one-click unsub + archive
                └──────────────────────────────────┘
```

Tune the buckets by editing the YAML files in `~/.gmail_cli/lists/` — no Python required.

---

## 🛠 The autopilot pipeline

```
gmail-cleanup autopilot
   │
   ├── Phase 1  filters apply        Declare categorization rules to Gmail (idempotent)
   ├── Phase 2  unsubscribe          Find recent noise, hit RFC 8058 one-click, archive
   ├── Phase 3  mark-read            Clear the archived-but-unread backlog
   └── Phase 4  verify               Audit previous unsubs; --escalate to block stuck ones
```

Each phase also works standalone. Autopilot is the convenience composition.

---

## 📖 Commands

| Command | What it does |
|---|---|
| **`setup`** | Interactive 7-step wizard: GCP credentials → OAuth → account registration. **Start here.** |
| **`autopilot`** | Full pipeline. The daily driver. `--days N` / `--min-count K` tune the unsubscribe phase; `--email-summary` emails the report to you (try it with `--dry-run`); `--all-accounts` runs across every configured Gmail. |
| `status` | Dashboard: live counts, filter inventory, list sizes, 7-day history |
| `stats` | Inbox count, unread, storage, oldest email |
| `top-senders --days N` | Rank senders by volume |
| `subscriptions` | Find senders with `List-Unsubscribe` headers |
| `unsubscribe --days N --min-count K` | One-click unsubscribe noise senders + archive their mail |
| `mark-read --query Q` | Bulk-mark messages as read (default: archived-but-unread backlog) |
| `verify [--grace-days N] [--escalate]` | Check whether senders kept mailing **after** you unsubscribed (plus a 2-day grace period); auto-block stuck senders |
| `attachments [--archive\|--delete]` | Find oversized old emails, rank by bytes |
| `filters apply / list` | Create/upgrade/list Gmail filters |
| `config show / init` | Manage `~/.gmail_cli/config.yaml` |
| `accounts list / add / remove` | Manage multi-account roster |
| `schedule install / uninstall / status` | Daily launchd-scheduled autopilot (macOS) |
| `archive` / `delete` / `label` | Bulk operations by sender / category / label / query / age |

All destructive commands prompt for confirmation unless you pass `--yes`. Global flags: `--quiet`, `--verbose`, `--all-accounts`.

---

## 🔐 Safety model

Four YAML lists govern behavior. Each one is the packaged seed (shipped inside the package) merged with your own copy in `~/.gmail_cli/lists/<name>.yaml`. Edit your copies to tune the tool — no Python required. Everything the tool writes goes to `~/.gmail_cli/lists/`, never into the installed package.

| File | Used by | Match | Seed ships | Behavior |
|---|---|---|---|---|
| [`keep.yaml`](gmail_cleanup/lists/keep.yaml) | `unsubscribe` | Substring | Populated | If sender matches, the unsubscribe is **refused**. Banks, healthcare, .gov, security senders. |
| [`kill.yaml`](gmail_cleanup/lists/kill.yaml) | `unsubscribe`, `filters apply` | Substring | Empty | Forces unsubscribe + archive regardless of message-count threshold |
| [`humans.yaml`](gmail_cleanup/lists/humans.yaml) | `filters apply` | Exact email | Empty | Star + mark important + spam-protect. Excluded from `has:list` catch-all |
| [`unsubbed.yaml`](gmail_cleanup/lists/unsubbed.yaml) | `filters apply`, `verify` | Exact email | Empty | Anti-resurrection — auto-archive if a previously-unsubscribed sender tries to come back. Written automatically after each successful unsubscribe. |

The unsubscribe flow prefers RFC 8058 one-click POST (the standard Gmail/Apple now require for bulk senders). Falls back to GET, then mailto. Senders without any `List-Unsubscribe` header are skipped, not silently archived — that's a guard against accidentally archiving a real person.

See [`gmail_cleanup/lists/README.md`](gmail_cleanup/lists/README.md) for the conflict-resolution rules between the four files.

---

## 👥 Multi-account

```bash
gmail-cleanup accounts add work@company.com   --label work
gmail-cleanup accounts add personal@gmail.com --label personal
gmail-cleanup accounts list

# Run the same command across every configured account:
gmail-cleanup autopilot --all-accounts
gmail-cleanup stats     --all-accounts
gmail-cleanup verify    --all-accounts
```

**Partial-failure semantics:** if one account errors, the others still run. Failures are reported at the end. Exit code = number of failed accounts (0 = all clean).

---

## 🤖 Daily autopilot (macOS)

```bash
# Install a launchd job that runs autopilot every day at 08:00 local:
gmail-cleanup schedule install --time 08:00 --escalate

# Check it's wired up:
gmail-cleanup schedule status

# Remove it:
gmail-cleanup schedule uninstall
```

Linux (systemd) and Windows (Task Scheduler) integrations are on the [roadmap](ROADMAP.md).

---

## 🛠 Development

```bash
pip install -e ".[dev]"
pytest                # 200+ tests, <1s
ruff check .          # lint
ruff format .         # format
```

CI runs pytest on Python 3.11/3.12/3.13 for every push and PR.

---

## 📚 Documentation

- [**`ARCHITECTURE.md`**](ARCHITECTURE.md) — 5-minute tour of the codebase
- [**`TROUBLESHOOTING.md`**](TROUBLESHOOTING.md) — common first-run issues
- [**`CHANGELOG.md`**](CHANGELOG.md) — version history
- [**`HANDOFF.md`**](HANDOFF.md) — current session state
- [**`ROADMAP.md`**](ROADMAP.md) — what's planned
- [**`CONTRIBUTING.md`**](CONTRIBUTING.md) — how to contribute
- [`gmail_cleanup/lists/README.md`](gmail_cleanup/lists/README.md) — list conflict-resolution rules
- [`docs/superpowers/specs/`](docs/superpowers/specs/) — design specs for major features
- [`docs/superpowers/plans/`](docs/superpowers/plans/) — implementation plans

---

## 🤝 Contributing

Issues, PRs, and discussion all welcome. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md) — it covers the safety invariants you must not break.

The cardinal rule: **the tool's job is to never unsubscribe you from your bank.** Anything that loosens the KEEP list semantics for convenience will be rejected.

---

## 📄 License

MIT — see [`LICENSE`](LICENSE).

---

<sub>Built by [Brian Gorzelic](https://github.com/bgorzelic). Safety-tested on a 7,283-email backlog before any of you used it.</sub>
