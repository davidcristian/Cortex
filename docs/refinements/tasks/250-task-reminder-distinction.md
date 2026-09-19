# A task versus reminder distinction on the pull surface

**Status:** open, dead until a consumer
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Trigger:** the surface must distinguish them (a task icon, a "task ran" label, a task-only action).
**Verified:** 2026-09-19

A fired task now rides the same `DueReminder`/`Reminders.tsx` card as a reminder, undistinguished:
`DueReminder` carries no `kind`, the overlay labels the stack "Due reminders" with a bell icon,
and the same taint/inert-text posture holds (a task outcome is a store row no output guardrail
saw, badged if tainted, nothing linkified), so the reuse is safe but a task outcome reads as a
reminder. Telling them apart wants a `kind` (or a distinct field) on `DueReminder` plus overlay
rendering, a proto + four-tree + overlay change. Deferred until the surface must distinguish them
(a different icon, a "task ran" label, a task-only action), not built speculatively.
**Read against the tree 2026-09-13, and narrower than it reads.** The push half already names the
kind: `_deliver` is handed `REMINDER_TITLE` ("Cortex reminder") for a reminder and `TASK_TITLE`
("Cortex task") for a task outcome (`ticker.py`), so a toast says which fired and only the pull
card does not. That also bounds who sees the gap, because a fired item reaches the pull card only
when its push did not show: a toast the body confirms is acked in the same call.
**And the hop count above is short.** A `kind` on `DueReminder` is written in
[proto/body.proto](../../../proto/body.proto), regenerated into both stubs, and then set and read
in `reminder_to_proto`
([reminders.py](../../../brain/packages/orchestrator/src/cortex_orchestrator/reminders.py)), the
body's own `DueReminder` struct
([session_types.rs](../../../body/crates/core/src/session_types.rs)) and the mapping in
[rpc/reminders.rs](../../../body/crates/rpc/src/reminders.rs), the shell's `WireReminder`
([src-tauri/reminders.rs](../../../body/app/src-tauri/src/reminders.rs)), and in the overlay the
`DueReminder` interface ([types.ts](../../../body/app/src/bridge/types.ts)), the demo bridge's
seeded rows ([demoScript.ts](../../../body/app/src/bridge/demoScript.ts)) and `Reminders.tsx`.

## Trail

- 2026-07-16: Opened behind the landing of task-outcome delivery, which reused the reminder card
  for a task's outcome with no wire change. The area held at 8 across that landing, one entry
  closing and this one opening behind it.
- 2026-09-13: re-derived and corrected. Every claim about the card holds: `DueReminder` carries no
  `kind` (`proto/body.proto`), `Reminders.tsx` labels the stack "Due reminders" behind a `BellIcon`
  and linkifies nothing, and a task's fire-time taint rides the same `tainted` field
  (`reminder_to_proto` maps `item.tainted`, which the store ORs the fire's taint onto). What the
  entry did not say is that the toast already names the kind through its title, so the gap is the
  pull card alone and only for a fire whose push did not show, and that the change crosses two more
  files than it counted. The trigger has not fired: nothing in the overlay asks which kind a row is.
- 2026-09-19: re-derived, and every claim holds. `DueReminder` still carries no `kind`,
  `Reminders.tsx` still labels the list "Due reminders" and draws a `BellIcon` on every row,
  `reminder_to_proto` still maps `item.tainted` and swaps in a task's `last_outcome` as the text,
  and `_deliver` is still handed `REMINDER_TITLE` or `TASK_TITLE`. The overlay files the hop list
  names are still the three that would change outside the tests (`types.ts`, `demoScript.ts`,
  `Reminders.tsx`); the other overlay readers of `DueReminder` pass it through. Nothing in the
  overlay asks which kind a row is, so the trigger has not fired. A different gap on the same card,
  a task's outcome lost to an ack rather than mislabelled, was fixed the same day ([ADR-0025
  addendum of this date](../../adr/ADR-0025-scheduling-reminders.md)).
