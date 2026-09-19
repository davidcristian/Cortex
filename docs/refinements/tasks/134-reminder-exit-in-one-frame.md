# A reminder leaving the stack in one frame

**Status:** done 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0034](../../adr/ADR-0034-panel-views.md)

`Collapse` wrapped the whole reminder stack, so the stack rolled shut when the last reminder was
acked, but acking one of three just deleted that row. The fix the entry named is a
`usePresence(items, key)` hook that keeps a removed item rendered until its own roll finishes,
which the switcher's rows would want too.

**Shipped 2026-08-03 as that hook** ([ADR-0035](../../adr/ADR-0035-console-and-motion.md)). The
entry was right about the fix and stale about the defect. Half of what it described had been
fixed on 2026-07-20 by the settings-tab slice, which wrapped each row in its own `Collapse`;
traced at 60Hz that roll is correct, the acked row running 57.25px to 0 while its neighbour
travels the same distance in the same frames. Nobody closed the entry.

What was left underneath was not motion and was worse than one row's worth of instant. That first
version held the row by holding the ack, behind a `setTimeout(MORPH_ROLL_MS)` whose unmount
cleanup cancelled it, and the stack is keyed to the chat it belongs to. Measured at 900x900 over
the demo bridge, acking the middle of three reminders and pressing Ctrl+N 100 ms later left all
three cards on screen, and a fresh summon listed all three again: the gesture had done nothing.
The same local list never forgot an id either, so a reminder that came back, which is what a lost
ack leaves behind, rendered into a `Collapse` that was already shut and stayed invisible for the
life of the panel.

`overlay/usePresence.ts` inverts it: the ack goes up in the frame the check is pressed, the
reducer drops the reminder as before, and the row is what is held, at the index it kept, until its
own `Collapse` reports the roll over through a new `onClosed`. The hook owns no clock, so
`MORPH_ROLL_MS` and `EASING` stay the one vocabulary, and it is written to be shared with the
switcher's rows, which are not wired to it.

Two live defects were repaired with the restructure, both unnoticed since the wrapper shipped: the
stack's `<ul>` had `<div>` children, so it was not a list to a screen reader, and the hairline
between two rows is an adjacent-sibling rule that two rows in two wrappers cannot satisfy, so it
had been off (computed `border-top-width` 0px on all three rows; the stack now measures 187.75px
where it measured 185.75px, which is the two restored hairlines).

One lesson outlasts the feature: the hook's first shape remembered its last render by writing a
ref during the render, passed every test written against it, and dropped the row on the first
frame in a real browser, because `StrictMode` invokes a render twice and the second pass read back
what the first had written. A hook deriving from what it rendered last has to mean the last
commit, and only an effect knows which render that was.

## History

- 2026-07-19: Filed with the panel's views as one row's worth of instant against a smooth panel,
  deferred as genuinely small rather than as invisible.
- 2026-07-20: The settings-tab slice wrapped each row in its own `Collapse` the day after the
  entry was written, so half of what it described was fixed and nobody closed the entry.
- 2026-08-03: Shipped as the `usePresence` hook, over a defect that was a lost ack rather than
  motion, and it left the switcher's rows unwired as a new deferral, so the area count held at 18.
  An entry filed as cosmetic turned out to cover a lost user gesture, so it underestimated what it
  was worth rather than what it would take. The overlay's hooks are tested under `StrictMode` now.
