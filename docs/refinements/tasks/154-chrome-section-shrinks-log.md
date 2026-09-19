# A section outside the history shrinking the log

**Status:** done 2026-08-04
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

The switcher list and the reminder stack open outside the history, so at the panel's maximum
height their growth takes space from the history's window rather than from the panel, and
`overlay/logRide.ts` never heard them: it listened on the history box, and the start event went to
the panel. Measured 2026-08-03 at 640x720 on a full history: opening the chat switcher took the
history's window from 293px to 73px with `scrollTop` left at 408, so the reader's distance from
the end of the reply went from 3px to 223px.

Fixed by moving the subscription from the history box to the column the panel renders into, and by
reading the opening element off the event's target so two animations in one frame stay apart. One
more rule was needed: the limit that keeps an opening section's own top edge on screen only applies
when `box.contains(section)`, because a section outside the history is not something the reader can
be scrolled away from. Without that line the scroll position froze where it started.

Afterwards, per painted frame: the distance from the end reads 3px on all 19 frames of the
switcher opening and all 19 of it closing, `scrollTop` runs 173 to 393 and back to the same pixel,
no frame moves it more than 34px, and it all happens inside the animation's 300ms. Three panel
motions were measured alongside and are all correct: a switcher opened 100ms into a summon, Ctrl+N
on a full history with the list open, and acknowledging a reminder. A reader who has scrolled up is
still left alone.

Measuring note: read inside a `requestAnimationFrame` callback the scroll looks one frame behind,
because those callbacks run before this one. Read it in the `ResizeObserver` step instead.

## History

- 2026-08-03: Opened when the scroll fix above was committed, being the same defect from the other
  side.
- 2026-08-04: Closed. The diagnosis reproduced exactly, but wiring the existing code up to the new
  event changed nothing until the `box.contains(section)` rule was added. The reminder stack turned
  out never to cost the reader anything (it only shows on an empty log); what does reach the log is
  any row inside either list, since they all animate through the same component.
