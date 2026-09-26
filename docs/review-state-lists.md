# Review: `state.py` and `lists_io.py`

Scope: `gmail_cleanup/state.py`, `gmail_cleanup/lists_io.py`, and the new
`gmail_cleanup/atomic_io.py` helper they share. Every finding below was
reproduced against the pre-fix code before being fixed; reproductions are
inlined and each has a matching test in `tests/test_review_findings.py`.

Reviewed on the `review` worktree at commit `75dbd04`.

## Summary

| # | Finding | Module | Severity | Fixed |
|---|---------|--------|----------|-------|
| 1 | Unterminated header comment swallows an appended sender | `lists_io` | High — silent data loss | yes |
| 2 | Fixed temp name + unsynchronised read-modify-write | both | High — lost records and crashed commands | yes |
| 3 | Failed rename strands the only copy of the new data | both | Medium — unrecoverable data + litter | yes |
| 4 | `deltas` can overwrite the event's own `at`/`source` | `state` | Low — latent | yes |
| 5 | `read_state` only guarded `JSONDecodeError` | `state` | Low — crash on a bad file | yes |
| 6 | Comments after the first entry are dropped | `lists_io` | Accepted trade-off | no — see below |
| 7 | Sanitised email paths can collide | `state` | Theoretical | no — see below |
| 8 | Shared temp file can interleave into corrupt JSON | both | Not reproducible | n/a |

## 1. An unterminated header comment silently swallows an appended sender

`append_to_unsubbed` rebuilt the file as `header + body`, but nothing
guaranteed the preserved header ended in a newline. A file whose last comment
line was unterminated — a hand-edited file, or a list emptied down to its
comments — glued the first new entry onto that comment line, so YAML parsed the
whole line as a comment:

```
append_to_unsubbed returned: ['victim@example.com']
file contents  : '# Auto-managed by gmail-cleanup.- victim@example.com\n'
yaml.safe_load : None
```

`append_to_unsubbed` reported the sender as added and `cmd_unsubscribe` printed
`📝 Added 1 sender(s) to lists/unsubbed.yaml`, but the record was never in the
list. It was unrecoverable afterwards too: the next append produced a valid file
containing only the newer sender.

This matters because `lists/unsubbed.yaml` is what the
`previously-unsubscribed → 💬 Notifications + archive` filter and the `verify`
subcommand read. A silently dropped entry means a sender the user unsubscribed
from can resume mailing without being filtered, while the CLI reported success.

Fix: `_read_header_and_body` now guarantees its header ends in a newline.

## 2. Fixed temp name and an unsynchronised read-modify-write

Both writers derived one fixed temp path from the target (`.json.tmp` /
`.yaml.tmp`), and nothing held a lock across the read and the write. A daily
launchd autopilot (`gmail_cleanup/scheduler.py:23`) and a manual command can
touch the same account at once, and `append_event` has no caller-side exception
handling (`gmail_cleanup/__init__.py:725`, `:1200`, `:1237`).

Six real processes, five appends each — 30 expected:

```
BEFORE  events recorded : 10 (expect 30)   exit codes: [0, 1, 1, 0, 1, 1]
        senders recorded:  7 (expect 30)   FileNotFoundError: unsubbed.yaml.tmp -> unsubbed.yaml
AFTER   events recorded : 30               exit codes: [0, 0, 0, 0, 0, 0]
        senders recorded: 30
```

Two separate defects, both real:

- A shared temp name, so a sibling's rename removed the file the loser was about
  to rename. Four of six processes died with `FileNotFoundError` — the entire
  command exited non-zero *after* the Gmail work was already done.
- No mutual exclusion, so writers that read before a sibling's rename silently
  discarded that sibling's write.

Fix: `atomic_io.file_lock` holds an exclusive `flock` across the whole
read-modify-write, and `atomic_io.atomic_write` uses a unique temp file per
write. Verified at both the thread and process level.

## 3. A failed rename stranded the only copy of the new data

`tmp.write_text(...)` followed by `tmp.replace(path)` left the temp file in
place when the rename failed or the process died between the two steps, and the
next run overwrote it. The newer version existed nowhere else:

```
real file : '# h\n- old@example.com\n'
leftovers : ['unsubbed.yaml', 'unsubbed.yaml.tmp']
tmp holds : '# h\n- old@example.com\n- new@example.com\n'
after next run: '- old@example.com\n- newer@example.com\n'   # 'new' is gone for good
```

`state.append_event` behaved the same way, leaving
`~/.gmail_cli/state_<email>.json.tmp` as the sole copy of the event.

Fix: `atomic_write` removes its own temp file if anything fails. Recovery of a
temp file stranded by a hard kill (`SIGKILL`, power loss) is deliberately *not*
implemented — see "Known gaps".

## 4. `deltas` could overwrite the event's own `at` and `source`

`append_event` built the event as `{'at': now, 'source': source, **deltas}`, so
a delta key of `at` or `source` won:

```
append_event('d@example.com', 'autopilot', {'at': 'not-a-timestamp', 'source': 'spoofed'})
stored event      : {'at': 'not-a-timestamp', 'source': 'spoofed'}
last_autopilot_at : 2026-09-26T03:59:02+00:00
```

`cmd_status` rolls its 7-day window off that `at`
(`gmail_cleanup/__init__.py:372`), so a clobbered timestamp drops the event out
of the dashboard while `last_autopilot_at` still shows the real time — the two
disagree with no error. No current call site passes those keys, so this is
latent, but `at` and `source` are the record's own fields and now always win.

## 5. `read_state` only guarded `json.JSONDecodeError`

Three reachable crashes, all silent in the sense that nothing caught them:

- Stray non-UTF-8 bytes raised `UnicodeDecodeError` out of `cmd_status`.
- A state file holding a JSON list made `append_event` raise
  `AttributeError: 'list' object has no attribute 'setdefault'`.
- A `history` that was not a list raised `AttributeError: ... has no attribute
  'append'`.

Both `AttributeError`s fire *after* the Gmail work is done, with no caller-side
handler, so the command dies having already unsubscribed or archived.

Fix: `_read_state_file` normalises the shape and tolerates undecodable content.
`FileNotFoundError` and `ValueError` (which covers both `JSONDecodeError` and
`UnicodeDecodeError`) fall back to the default; other `OSError` subclasses
(permissions, a directory in the file's place) still propagate, because
silently resetting a file we could not read would hide a real misconfiguration.

## 6. Comments after the first entry are dropped — accepted, not fixed

`_read_header_and_body` stops at the first non-comment line, so a comment
anywhere below the first entry is lost on rewrite:

```
'- keep@x.com\n# trailing note'  ->  '# Auto-managed by ...\n- keep@x.com\n- new@x.com\n'
```

This is a documented trade-off, not a bug: the design spec
(`docs/superpowers/specs/2026-05-15-gmail-cleanup-v0.5-design.md:90`) accepts
"loses YAML comment ordering on write". Fixing it would mean hand-rolling YAML
emission and re-implementing PyYAML's quoting. Unchanged.

## 7. Sanitised email paths can collide — theoretical, not fixed

```
a/b@example.com -> state_a_b@example.com.json
a_b@example.com -> state_a_b@example.com.json     # same file
```

`/` and `\` both map to `_`, so two distinct accounts would share one state
file. Not reachable in practice: `/` is not legal in an email address
(RFC 5321), and accounts come from config rather than untrusted input. Path
traversal is not possible — the `state_` prefix means `../../etc/passwd` becomes
`~/.gmail_cli/state_.._.._etc_passwd.json`, verified. Left alone; hashing the
local part would be the fix if this ever mattered.

## 8. Shared temp file interleaving into corrupt JSON — not reproducible

The plausible worst case for finding 2 is two writers interleaving into the one
shared temp file, leaving unparseable JSON. I could not produce it: 200
threaded attempts against a pre-seeded state file left the file parseable every
time, because `write_text` truncates and writes fast enough that the window did
not materialise. The observable symptom is the `FileNotFoundError` crash in
finding 2, not corruption. Reported as unproven rather than fixed.

## Also checked, no defect found

- `HISTORY_MAX` truncation keeps the **newest** 30 entries and preserves order.
- Per-account state isolation: distinct emails get distinct files; only the
  unreachable `/`-collision in finding 7 merges them.
- `append_to_unsubbed` dedup is case-sensitive and literal. Intentional — the
  Gmail filter built from this list is generated by `gmail_cleanup`, which
  lowercases addresses via `_extract_email` (`gmail_cleanup/__init__.py:486`),
  so the stored casing does not change what the filter matches.
- Intra-call duplicates: `existing_set` is updated inside the loop, so
  `['a@b', 'a@b']` in one call adds one entry and returns one entry.
- Entries are written as YAML strings; `safe_dump` re-quotes anything that would
  otherwise round-trip as a non-string (e.g. `'12345'`).
- `path.with_suffix()` cannot mangle the temp name: the target always ends in
  `.json`/`.yaml`, so the suffix is always that one.
- `append_to_unsubbed` is wrapped in `except (OSError, ValueError)` at
  `gmail_cleanup/__init__.py:720`, so a bad list file warns instead of crashing.
  `append_event` has no such wrapper — see Known gaps.

## Known gaps left open deliberately

- **`append_event` failures are unhandled by callers.** `cmd_unsubscribe`,
  `cmd_autopilot`, and `cmd_mark_read` call it with no `try`. A state-write
  failure still kills the command after the Gmail work succeeded. Findings 2 and
  3 make it far less likely, but the missing handler is a separate defect in
  `gmail_cleanup/__init__.py`, outside this review's scope.
- **A state file that parses but has the wrong shape is reset, not repaired.**
  This matches the pre-existing `JSONDecodeError` behaviour, so it is not a new
  class of loss, but the malformed file is overwritten with no `.corrupt` copy
  kept. Preserving one would be a better answer; it is a behaviour change, so
  it is left for a decision rather than slipped into a bug fix.
- **`atomic_write` changes the file mode to 0600** (from `mkstemp`; the old
  `write_text` produced 0644). Both files hold email addresses, so 0600 is the
  better default, and git does not track the difference — but it is visible on
  disk.
- **Temp files from a hard kill are not reclaimed.** `atomic_write` cleans up
  failures it can see; a `SIGKILL` between write and rename leaves an
  unreferenced `*.tmp` in the directory. Recovery would mean scanning for stale
  temps at startup, which risks resurrecting a version a concurrent writer is
  still using.
- **`file_lock` creates the parent directory** so the lock file can sit beside
  its target. For `state.py` that is pre-existing behaviour. For `lists_io` a
  missing `lists/` is now created rather than raising — which only happens on an
  already-broken install, where the packaged lists are missing anyway.
- **`*.lock` was added to `.gitignore`.** `.gmail_cli/` was already covered, but
  the lock beside `lists/unsubbed.yaml` would otherwise show as untracked.

## Verification

```
uv run --with-requirements requirements.txt --with pytest pytest -q
106 passed

uv run --with-requirements requirements.txt --with pytest \
    pytest tests/test_review_findings.py -q      # against pre-fix sources: 16 failed, 6 passed
```

The 6 that pass pre-fix are regression guards for behaviour that was already
correct (`HISTORY_MAX` cap, header still first, deltas still recorded, no temp
file after a *successful* write, truncated JSON already handled). The other 16
each fail without their fix.

`ruff check .` reports 97 errors both before and after these changes, so no new
lint was introduced. `ruff format` is not enforced in this repo — it would
rewrite 21 files to double quotes, and the codebase uses single quotes.

Concurrency tests were run 25 times with no flakes; they assert outcomes
(events recorded, senders present) rather than timing, and join with a timeout
that fails rather than hanging.
