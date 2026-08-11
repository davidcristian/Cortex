# A task versus reminder distinction on the pull surface

**Status:** open, dead until a consumer
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Trigger:** the surface must distinguish them (a task icon, a "task ran" label, a task-only action).

A fired task now rides the same `DueReminder`/`Reminders.tsx` card as a reminder, undistinguished:
`DueReminder` carries no `kind`, the overlay labels the stack "Due reminders" with a bell icon,
and the same taint/inert-text posture holds (a task outcome is a store row no output guardrail
saw, badged if tainted, nothing linkified), so the reuse is safe but a task outcome reads as a
reminder. Telling them apart wants a `kind` (or a distinct field) on `DueReminder` plus overlay
rendering, a proto + four-tree + overlay change. Deferred until the surface must distinguish them
(a different icon, a "task ran" label, a task-only action), not built speculatively.

## Trail

- 2026-07-16: Opened behind the landing of task-outcome delivery, which reused the reminder card
  for a task's outcome with no wire change. The area held at 8 across that landing, one entry
  closing and this one opening behind it.
