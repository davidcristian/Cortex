# An exit for the switcher's rows

**Status:** landed 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opened
2026-08-03 with the reminder stack's per-row exit ([ADR-0035
addendum](../../adr/ADR-0035-console-and-motion.md)). Deleting a chat drops its row from
`state.sessions` the moment the write lands, so it goes in a frame and the rows under it snap up,
which is the defect the reminder stack no longer has. `overlay/usePresence.ts` is generic and was
built to be shared, so the missing part is the wiring rather than the mechanism. What makes it a
second surface rather than a free line: the row needs the same restructure the reminder row got
(the `<li>` outside the roll, the row's box inside it), and the switcher's own rules have to be
re-checked against that wrapper, `.switcher-li:hover .switcher-rename-btn` and its two siblings
reaching for descendants, `.switcher-li.pinned` styling the row itself, and a row that is
mid-rename or mid-delete-confirm being a different subtree of the same slot. It also wants its own
frame trace, since a delete refreshes the list behind the roll and resets the panel outright when
the chat being deleted is the one on screen. Nothing blocks it.
- **LANDED 2026-08-03, the same day it was opened, and the wiring was about half of it**
  ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). The defect was as described and
  measured worse than it reads: at 900x900 the card went 164 to 114 between one frame and the
  next, the row below jumping y=270 to y=220, with the panel and the composer not moving at all,
  so that single snap was the whole visible event. What the entry did not have is the part that
  made this a decision rather than a wiring. **The hook needed a change.** It put a departed row
  back at the INDEX it held, which is exactly right for a list that only ever loses rows, and the
  switcher re-lists pinned-first and then by recency after every write, so a pin, a finished turn
  or a summon refresh can reorder it around a row that is still rolling. `Leaving` now carries the
  key of the row above it as well, and a departed row goes back under that key when it is still on
  screen, the index surviving as the fallback for a neighbour released first or dropped by a whole
  re-listing. Traced with a pin landing 120ms into a delete: by neighbour the rolling row travels
  y=220 to y=270 with the row it sat under, by index it stays at y=220 and that neighbour walks
  down past it to y=240.47. Two of the three hazards the entry named were real and one was not:
  the `<li>` does have to come out of the roll, but not for the hairline (the switcher draws none
  between rows) and not for the hover, pinned, rename or confirm rules either, all four of which
  read down to a descendant and follow `.switcher-row` inside the wrapper unchanged. The reason it
  has to come out is the one the entry missed, `min-height: 50px` on the outside of a roll being a
  floor the roll cannot get under; put back deliberately, the row stands at 50.00 for the whole
  300ms and then vanishes in one frame, which is the old defect arriving 300ms late. Two more
  things the entry did not have: a row held on screen after its chat is gone is 300ms of live
  buttons offering to open and re-delete a deleted chat, so the slot is `withdrawn` while it
  leaves; and the demo bridge's `deleteSession` was a no-op over its held list while rename and
  pin both stuck, which made the exit unmeasurable by hand, the refresh behind the delete listing
  the chat straight back. It deletes now, and seeds a third chat so a middle row has neighbours on
  both sides. The exit itself measures 50.00px to zero over 300ms with the row below travelling
  269.63 to 220.00 and the row above holding at 170.00, the panel and composer 0px throughout, and
  at 640x720, where the list is at its cap, the card holds 135.14 until the content falls under
  the cap and the rows travel inside their own scroll box meanwhile.

## Trail

- 2026-08-03: Opened as the reminder stack's per-row exit landed and left the generic hook behind
  for it, which is the backlog working as intended, and the area's count held over the pair.
- 2026-08-03: Closed the same day by wiring the switcher to that same hook, and it was about half of
  the wiring it called itself, the shared hook having had to learn that a list can reorder under a
  row that is still leaving. Two of the three hazards the entry named did not apply and the one that
  mattered was not on its list.
