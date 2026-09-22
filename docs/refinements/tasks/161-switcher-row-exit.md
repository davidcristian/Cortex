# An exit animation for the switcher's rows

**Status:** done 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Deleting a chat dropped its row from `state.sessions` as soon as the write finished, so the row
vanished in one frame and the rows under it jumped up. Measured at 900x900: the card went from 164
to 114 between one frame and the next, with the row below jumping from y=270 to y=220, while the
panel and composer did not move.

Fixed by wiring the switcher to `overlay/usePresence.ts`, the same hook the reminder stack uses.
The hook needed a change first: it put a departing row back at the index it held, which is correct
only for a list that never reorders, and the switcher re-sorts after every write, putting hoisted
chats first and the rest by recency. `Leaving` now also records the key of the row above,
and a departing row goes back under that key while it is still on screen, with the index as a
fallback.

The `<li>` also had to move outside the animated box, but not for the reason the entry gave: its
`min-height: 50px` is a lower limit the shrink cannot get under, so the row stood at 50.00px for
the full 300ms and then vanished in one frame. The hover, `hoisted`, rename and confirm CSS rules
all read down to a descendant and worked unchanged. A row kept on screen after its chat is gone is
300ms of live buttons offering to open a deleted chat, so the slot is `withdrawn` while it leaves.

The exit measures 50.00px to zero over 300ms, with the row below travelling 269.63 to 220.00 and
the row above holding at 170.00, and the panel and composer not moving.

## History

- 2026-08-03: Opened when the reminder stack's per-row exit was committed and left the shared hook
  available.
- 2026-08-03: Closed the same day. It was about half the wiring it called itself, because the shared
  hook had to learn that a list can reorder under a row that is still leaving. The demo bridge's
  `deleteSession` was also a no-op, which had made the exit impossible to see by hand.
