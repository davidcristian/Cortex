# A task versus reminder distinction on the pull surface

**Status:** open, waiting for a consumer
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Trigger:** the surface must distinguish them (a task icon, a "task ran" label, a task-only action).
**Verified:** 2026-09-19

A fired task uses the same `DueReminder` and `Reminders.tsx` card as a reminder, with nothing to
tell them apart: `DueReminder` has no `kind`, and the overlay labels the list "Due reminders" with
a bell icon. The reuse is safe, since a task outcome is a store row that no output check saw,
marked if tainted and never turned into links, but a task outcome reads as a reminder. Telling them
apart needs a `kind` (or a separate field) on `DueReminder` plus overlay rendering.

The gap is narrower than it first looked. The push half already names the kind: `_deliver` is given
`REMINDER_TITLE` ("Cortex reminder") for a reminder and `TASK_TITLE` ("Cortex task") for a task
outcome (`ticker.py`), so a toast says which fired and only the pull card does not. That also
bounds who sees it, because a fired item reaches the pull card only when its push did not show; a
toast the body confirms is acked in the same call.

The change touches: [proto/body.proto](../../../proto/body.proto), regenerated into both stubs;
`reminder_to_proto`
([reminders.py](../../../brain/packages/orchestrator/src/cortex_orchestrator/reminders.py)); the
body's `DueReminder` struct
([session_types.rs](../../../body/crates/core/src/session_types.rs)) and the mapping in
[rpc/reminders.rs](../../../body/crates/rpc/src/reminders.rs); the shell's `WireReminder`
([src-tauri/reminders.rs](../../../body/app/src-tauri/src/reminders.rs)); and in the overlay the
`DueReminder` interface ([types.ts](../../../body/app/src/bridge/types.ts)), the demo bridge's
seeded rows ([demoScript.ts](../../../body/app/src/bridge/demoScript.ts)) and `Reminders.tsx`.

## History

- 2026-07-16: Opened behind task-outcome delivery, which reused the reminder card for a task's
  outcome with no wire change.
- 2026-09-13: Checked against the tree and corrected. Every claim about the card holds. What the
  entry did not say is that the toast already names the kind through its title, so the gap is the
  pull card alone and only for a fire whose push did not show, and that the change touches two more
  files than it counted. The trigger has not occurred.
- 2026-09-19: Checked again and every claim holds. `DueReminder` still has no `kind`,
  `Reminders.tsx` still labels the list "Due reminders" and draws a `BellIcon` on every row,
  `reminder_to_proto` still maps `item.tainted` and substitutes a task's `last_outcome` as the
  text, and `_deliver` is still given `REMINDER_TITLE` or `TASK_TITLE`. The three overlay files
  listed above are still the ones that would change outside the tests; the other overlay readers of
  `DueReminder` pass it through. Nothing in the overlay asks which kind a row is. A different
  problem on the same card, a task's outcome lost to an ack rather than mislabelled, was fixed the
  same day ([ADR-0025](../../adr/ADR-0025-scheduling-reminders.md) decision 5).
