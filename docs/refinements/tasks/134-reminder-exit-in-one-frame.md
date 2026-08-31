# A reminder leaving the stack in one frame

**Status:** landed 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0034](../../adr/ADR-0034-panel-views.md)

`Collapse` wraps the whole
stack, so the stack rolls shut when the last reminder is acked, but acking one of three just
deletes that row. The history absorbs the slack rather than jerking the composer, so what is left
is one row's worth of instant against a smooth panel.
Fixing it properly is a `usePresence(items, key)` hook that keeps a removed item rendered until
its own roll finishes, which the switcher's rows would want too. Deferred as genuinely small
rather than as invisible: it is one row, and the surrounding motion no longer amplifies it.
- **LANDED 2026-08-03 as the hook this entry named, and the entry was stale about the defect
  while being right about the fix** ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)).
  Half of what it describes had been fixed on 2026-07-20, the day after it was written, by the
  settings-tab slice: the stack has wrapped each ROW in its own `Collapse` since then, and traced
  at 60Hz that roll is the right one, the acked row running 57.25px to 0 while its neighbour
  travels the same distance in the same frames. Nobody closed the entry. What was left underneath
  it was not motion at all and was worse than "one row's worth of instant": that first version
  held the row by holding the ACK, behind a `setTimeout(MORPH_ROLL_MS)` whose unmount cleanup
  cancelled it, and the stack is keyed to the chat it belongs to. Measured at 900x900 over the
  demo bridge, acking the middle of three reminders and pressing Ctrl+N 100ms later left all three
  cards on screen and a fresh summon listed all three again: the gesture had done nothing. The
  same local list never forgot an id either, so a reminder that came back, which is exactly what a
  lost ack leaves behind, rendered into a `Collapse` that was already shut and stayed invisible
  for the life of the panel. `overlay/usePresence.ts` inverts it: the ack goes up in the frame the
  check is pressed, the reducer drops the reminder as it always did, and the ROW is what is held,
  at the index it kept, until its own `Collapse` reports the roll over through a new `onClosed`.
  The hook owns no clock, `MORPH_ROLL_MS` and `EASING` staying the one vocabulary, and it is
  written to be shared with the switcher's rows, which are not wired to it (a new deferral,
  below). Two repairs came with the restructure, both live and unnoticed since the wrapper landed:
  the stack's `<ul>` had `<div>` children, so it was not a list to a screen reader, and the
  hairline between two rows is an adjacent-sibling rule that two rows in two wrappers cannot
  satisfy, so it had been switched off (computed `border-top-width` 0px on all three rows; the
  stack now measures 187.75px where it measured 185.75px, which is the two restored hairlines
  exactly). One lesson is worth more than the feature: the hook's first shape remembered its last
  render by writing a ref DURING the render, passed every test written against it, and dropped the
  row on the first frame in a real browser, because `StrictMode` invokes a render twice and the
  second pass read back what the first had written. A hook deriving from what it rendered last
  time has to mean the last COMMIT, and only an effect knows which render that was.

## Trail

- 2026-07-19: Filed with the panel's views as one row's worth of instant against a smooth panel,
  deferred as genuinely small rather than as invisible.
- 2026-07-20: The settings-tab slice wrapped each row in its own `Collapse` the day after the entry
  was written, so half of what it described was fixed and nobody closed the entry.
- 2026-08-03: Landed as the `usePresence` hook the entry named, over a defect that was a lost ack
  rather than motion, and it left the switcher's rows unwired as a new deferral, so the area count
  held at 18. An entry filed as cosmetic turned out to be covering a lost user gesture, which is the
  mirror image of this backlog's usual lesson about cost estimates: it underestimated what it was
  worth rather than what it would take. Two live defects found by measuring rode along, the stack's
  `<ul>` having `<div>` children and the hairline between two rows having been off since 2026-07-20.
  The hook's first shape taught that a hook deriving from what it rendered last has to mean the
  last commit, since `StrictMode` invokes a render twice, and the overlay's hooks are tested under
  it now.
