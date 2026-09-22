# Two overlay modules over the 300-line cap

**Status:** done 2026-07-20
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Two overlay modules were over the 300-line cap, which the TypeScript trees were not checked
against by any script. Both were split along the lines the entry predicted.

`overlayState.ts` went from 394 to 241 by handing the turn-event fold to `overlay/turnState.ts`
(171 lines: `Message`, `PendingConfirm`, `CAPTURE_SCREEN_TOOL`, `submit`, `applyEvent` and its
helpers, `isTurnActive`, `latestReply`), which re-enters through the same re-export
`sessionState.ts` uses, so no call site moved. `useOverlay.ts` went from 321 to 181 by handing the
chat catalog to `overlay/useSessionCatalog.ts` (170 lines: the list refresh and its two triggers,
cold-start adoption, `openSession`, `renameSession`, `deleteSession`, `setSessionHoisted`,
`cyclePrev` and `cycleNext`), whose members the controller spreads in,
so a component still sees one flat interface. The turn half kept what a turn is and gained
`abandonTurn`, the deny-then-close pair that four call sites had written out by hand.

At the time `scripts/linecap.py` scanned `.py` and `.rs` only, so nothing automated changed.

**Corrected 2026-08-03: the claim that the cap was met held for one day.** The count of two was
true when it was written, but on 2026-07-21 `overlay/panelPlacement.ts` went to 304 and then to
371, and stayed over the cap for thirteen days, until the `ResizeObserver`
work took it to 295 on 2026-08-03 as a side effect. Nothing measured the cap, so it stopped being
met as soon as nobody was watching. The cap has been checked over `.ts` and `.tsx` since
2026-08-03 ([ADR-0011](../../adr/ADR-0011-body-v1.md) decision 12).

## History

- 2026-07-20: Opened and closed the same day, both modules split along the two lines the entry
  named and both re-entering through the module they left, so no call site moved.
- 2026-08-03: Its closing claim was corrected, and the cap became a check over `.ts` and `.tsx`,
  after a review found `scripts/linecap.py` had scanned `.py` and `.rs` only for thirty-three days.
