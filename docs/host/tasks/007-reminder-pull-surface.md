# The reminder pull surface on the hotkey path

**Status:** never attempted
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md)

**What only this proves.** That the card stack validated in the browser reads correctly at real
window size, and that a failed pull does nothing on the live path rather than emptying the surface.
[runbooks/scheduling.md](../../runbooks/scheduling.md) has the procedure and says the same: what is
host-side is the real hotkey path, whether the stack reads well over the live window and whether
killing the brain mid-session leaves the cards in place, which it should, since a failed pull
dispatches nothing.

**Do.** Summon the overlay with something due. Read the stack. Then stop the brain (`just down`)
and summon again.

**Pass.** The card stack sits above the history; each card has its text, how long ago it fired,
`repeats` on a recurring series, and a dashed, faintly red-tinted `untrusted source` badge when
tainted. Dismissing a card acknowledges it. With the brain down, the cards stay.

**Fail.** Cards vanishing when the brain goes away means a failed pull is clearing state, which is
the regression this check exists to catch.

**Record it.** Edit [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md) in place where its
Consequences name the look of a real card; then delete this section.

## Notes

- The session doc numbers this check **5**; ADR-0066 links the section that lists it.
- It pairs with the reminder toast check and uses the same seeded reminder.
- It had no backlog line until 2026-07-19, though it was never unrecorded:
  [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)'s host line has named the overlay's
  reminder surface on the real hotkey path since the slice was added, and the procedure is in the
  runbook.
