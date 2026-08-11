# Two overlay modules over the 300-line cap

**Status:** landed 2026-07-20
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

**Two overlay modules are over the 300-line cap the TypeScript trees are not machine-gated at.**
**Both were split along exactly the seams predicted here.** `overlayState.ts`
went from 394 to 241 by handing the turn-event fold to `overlay/turnState.ts` (171: `Message`,
`PendingConfirm`, `CAPTURE_SCREEN_TOOL`, `submit`, `applyEvent` and its helpers, `isTurnActive`,
`latestReply`), which is the third file to leave the way `sessionState.ts` did and re-enters
through the same re-export, so no call site moved. `useOverlay.ts` went from 321 to 181 by
handing the chat catalog to `overlay/useSessionCatalog.ts` (170: the list refresh and its two
triggers, cold-start adoption, open, rename, delete, pin, cycle), whose members the controller
spreads in verbatim, so a component still sees one flat interface. The turn half kept what a turn
is and gained `abandonTurn`, the deny-then-close pair that four call sites had written out by
hand and the catalog needs. `scripts/linecap.py` still scans `.py` and `.rs` only, so nothing
machine-enforced changed; what changed is that AGENTS.md's cap, which is about cognitive load and
does not care which toolchain a file is in, is now met.

**Corrected 2026-08-03: "is now met" held for one day.** The entry's count of two was true when
it was written, and its closing claim stopped being true on 2026-07-21, when
`overlay/panelPlacement.ts` went to 304 (`9e2ec6c3`) and then 371 (`051e733d`) and stayed over
the cap for thirteen days, until the ResizeObserver work took it to 295 on 2026-08-03 as a side
effect rather than because anything complained. That is exactly the failure mode the sentence
before it described: a cap met by attention is met until attention moves on. The cap is machine
enforced over `.ts`/`.tsx` from 2026-08-03 ([ADR-0011](../../adr/ADR-0011-body-v1.md) line-cap
addendum), so this line is the historical record of that interval rather than a standing
description.

## Trail

- 2026-07-20: Opened and closed the same day, both modules split along the two seams the entry named
  and both re-entering through the module they left, so no call site moved.
- 2026-08-03: Its closing claim that AGENTS.md's cap "is now met" was corrected. It held for one
  day: `overlay/panelPlacement.ts` went to 304 and then 371 on 2026-07-21 and stayed over the cap
  for thirteen days, until the `ResizeObserver` work took it to 295 as a side effect. The cap is
  machine enforced over `.ts`/`.tsx` from that day, after a review found `scripts/linecap.py` had
  scanned `.py` and `.rs` only for thirty-three days.
