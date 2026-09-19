# The composer's growth is the one resize never eased

**Status:** done 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

`usePanelMotion` is driven by renders of `Panel` and by a roll's end event, and the draft lives in
`Composer`'s own state, so a field growing a line re-renders nothing above the composer and
`place` is never called. The panel's `auto` height simply follows in the frame the character is
typed, with the bottom edge held, so nothing slides under the hand and nothing eases either. That
was 16px a wrapped line ([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 17), and
the restack put a whole button row into the same unpainted frame.

Traced per animation frame at 640x720 with the reminder stack acked, reading the panel's top edge
across two consecutive samples with no third state between them:

- **16px**, a further line on an already-stacked pill (229 to 213). Unchanged, and the common case.
- **36px**, the character that restacks a one-line draft (281 to 245). The wrapping character
  always falls in the band decision 17 describes, so the field is still one line at the stacked
  width and only the button's row is new. The line it wrapped to arrives a few characters later as
  a separate 16px step.
- **52px**, one keystroke that restacks and adds a line at once (281 to 229). Shift+Enter on a
  one-line draft is the reachable case, a typed newline needing two lines at any width.
- **122px**, a paste that fills the field to its 120px ceiling from one line (281 to 159). The
  ceiling bounds the whole entry.

The send button and the pill's bottom edge are identical in every sample of all four (the button
read `top 547, left 541` throughout), which is why it shipped: it reads as a relayout under a
still hand rather than as a jump.

**Shipped 2026-08-03 on the observer [R-138](138-placement-for-stale-height.md) asked for**
([ADR-0035](../../adr/ADR-0035-console-and-motion.md)). All four steps are paced eases now,
re-measured at 640x720 with the stack acked, per animation frame, reading the panel's top edge
after the placement has run:

- A further line on an already-stacked pill: 148, 147.13, 143.11, 137.64, 134.61, 133.03, 132.28,
  132.02, 132.
- The character that restacks a one-line draft: 184, 182.02, 172.98, 160.75, 153.86, 150.33,
  148.61, 148.02, 148.
- A Shift+Enter that restacks and adds a line at once: 184, 181.14, 168.08, 150.41, 140.5, 135.34,
  132.88, 132.03, 132, largest single frame 17.67px against the 52 it was.
- A paste that fills the field to its ceiling: 184, 180.98, 168.19, 141.92, 118.2, 103.77, 95.05,
  89.92, 87.14, 86.06, 86, largest single frame 26.27px. That total is 98px rather than the 122
  this entry published, because the panel is on its own ceiling at that size and the history
  absorbs the other 24.

One thing that looked like a regression is not one: `requestAnimationFrame` runs before the resize
observer steps, so a trace taken there reads the frame's layout before the placement has had its
say and appears to show the panel jumping to the new height and back. A second observer reading
the same frame after the placement reads the old height with one animation attached (352 where the
rAF probe read 404), so the frame paints the height the panel had and eases from it.

What the growth costs the history is not part of this entry: the log holds its own tail across a
pill resize ([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 18).

## History

- 2026-07-20: Measured at 640x720 in four steps and filed rather than taken, being a panel-motion
  change rather than a composer one.
- 2026-08-03: Shipped on the same observer as the stale-placement entry, with which it shared the
  whole of its fix.
