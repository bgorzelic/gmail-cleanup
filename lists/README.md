# Lists

The four YAML files in this directory drive the safety model. They are the only
files you should need to edit to tune the tool for your inbox.

| File | Used by | Match semantics |
|---|---|---|
| `keep.yaml` | `unsubscribe` | Substring match against sender email. If matched, the unsubscribe is refused. **Never auto-unsubscribes a sender that matches the keep list.** |
| `kill.yaml` | `unsubscribe`, `filters apply` | Substring match against sender email. Overrides the auto-discovery threshold — any match is unsubscribed even if it sent only 1 message. |
| `humans.yaml` | `filters apply` | Exact email match. Gets a protective Gmail filter (star + important + spam-protect). Also excluded from the `has:list` catch-all so a real person never accidentally gets archived. |
| `unsubbed.yaml` | `filters apply`, `verify` | Exact email match. Anti-resurrection — if any of these senders try to come back, they're auto-archived to the Notifications label. The `verify` command checks each entry against current inbox to find stuck unsubscribes. |

## Editing rules

- Comments (`# …`) are preserved by hand-editing but **not** by any automated write the tool does to these files.
- Order doesn't matter.
- One entry per line, no quotes needed (YAML strings).
- Save the file. Changes take effect on the next CLI invocation — no restart needed.

## Conflict resolution

If a sender matches both `keep.yaml` and `kill.yaml`:
- The `unsubscribe` command treats killlist as the explicit override (you put it there on purpose, knowing what you're doing). It will unsubscribe.
- This is intentional. A few senders sit on the boundary (e.g., a job-alert email from a financial services company) and you may want to force-unsub them.

If a sender matches both `humans.yaml` and any of the noise lists:
- `humans.yaml` always wins. Real people are never auto-archived.
