# A chat restored in a fresh shell opens short of its end

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)
**Verified:** 2026-10-10

On the Linux shell on 2026-10-10, each of six fresh starts of the shell opened the restored chat
with its last one to three messages below the visible part of the log, until the reader scrolled or
a new message arrived
([readings](../../readings/store-and-process-restarts.md#following-a-reply-cut-by-a-restart)).
A line the page wrote at each call of `overlay/useLogScroll.ts` showed the one follow call of the
start running 0.11 s after the page loaded, with the log box 10 px tall and its content 109,232 px
tall while the window was still hidden, and no scroll event and no follow call after that. The
follow flag stayed set, so the next message put the log back on its end.

## What to do

Find the layout change that makes the content taller after the start's follow call (the window
taking its size, or a settled reply posing its box), and follow it while the flag is set. A
`ResizeObserver` on the log's inner column is one way, if it leaves a section's roll to
`overlay/logRoll.ts`, which stops at the section's top edge. Check it again on the Linux shell.

## History

- 2026-10-10: filed while reproducing R-819 on the Linux shell, where the log's place after a fresh
  start was seen to be a separate defect from the follow flag going off.
