# The reminder pull surface on the hotkey path

**Status:** never attempted
**Sitting:** windows-desktop
**Capability:** W
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

**Until 2026-07-19 this check had no backlog line**, though it was never unrecorded:
[ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)'s host line has named "the overlay's reminder
surface on the real hotkey→overlay path" since the slice landed, and the procedure is in the
runbook. What it lacked was a place that listed it as work still owed. (Corrected 2026-07-19: this
section first claimed the runbook paragraph was its only record, which its own "Record it" line
below refutes.)

**What only this proves.** That the browser-validated card stack reads correctly at real window
size, and that a failed pull is a no-op on the live path rather than an emptied surface.

Kept verbatim from [runbooks/scheduling.md](../../runbooks/scheduling.md), which carries the procedure:

> what is genuinely host-side is the real hotkey path: whether the stack reads well over the live
> window and whether killing the brain mid-session leaves the cards in place (it should: a failed
> pull dispatches nothing) rather than emptying the surface.

**Do.** Summon the overlay with something due. Read the stack. Then stop the brain (`just down`)
and summon again.

**Pass.** The card stack sits above the history; each card carries its text, how long ago it fired,
`repeats` on a recurring series, and a dashed, faintly red-tinted `untrusted source` badge when
tainted. Dismissing a card acks it. With the brain down, the cards stay.

**Fail.** Cards vanishing when the brain goes away means a failed pull is clearing state, which is
the specific regression this check exists to catch.

**Record it.** A dated addendum to [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md), whose
host line already names "the overlay's reminder surface on the real hotkey→overlay path"; then
delete this section.

## Notes

- The sitting doc numbers this check **5**, and ADR-0025 cites it by that number.
- The host index's roll call adds that it pairs with the reminder toast check and uses the same
  seeded reminder.
