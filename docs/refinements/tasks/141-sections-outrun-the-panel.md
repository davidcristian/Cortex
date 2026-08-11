# Two full sections outrun the panel

**Status:** landed 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

**A switcher and a reminder stack that are both full outrun the panel before the composer is
asked for anything.** `.switcher` may be `40vh` and `.reminders` `30vh`, each capped as if it
were alone with the panel, and at the body's 720px window that is 504px of a 547px panel with the
header (54px) and the hint strip (33px) still to place. The composer now yields down to one row
of field plus its button row before the panel's edge does
([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 19), which is what turned this from "the
pill and the hint strip are outside the panel" into "the hint strip is", and the pill's 84px
floor is where the yielding stops. Forced with the panel's ceiling overridden to 300px and a
draft at the field's ceiling: the pill floors at 84px with its text and its button inside it and
the hint strip 34.75px past the clipped edge, where at the real 640x720 with both sections full
everything is inside (the hint strip clears the edge by 1px, the same 1px it clears it by with an
empty field). The fix is a cap that knows about its neighbours, since the two `vh` numbers cannot
both be right at once; what makes it a deferral rather than a defect is that the sections are the
user's own transient chrome, both are dismissible, and the state needs a full list AND a full
stack AND a draft at the ceiling to reach. Measured 2026-07-20.
- **LANDED 2026-08-03 as the neighbour-aware cap this entry asked for, and the entry understated
  itself in three ways** ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). The two
  `vh` numbers are what this said they are, and everything the entry drew from them was too kind.
  **It is not a corner:** on the demo's own seed of two chats and three reminders, at the body's
  640x720 window, pressing the switcher button once put the hint strip 29.75px past the panel's
  clipped edge and moved the composer 30.75px down to get there. The 547 above is
  `openHeight(720)`, the ceiling of a panel pinned 86px off the bottom of the screen, and this
  state does not pin it there: measured on that seed the panel stands 450px tall on a 184px edge,
  and on a widened one 436px on a 198px edge. The entry's arithmetic was against a taller panel
  than the one the harm happens in, which is why its conclusion came out one section too
  generous.
  **It is not bounded at the hint strip:** with both sections at their caps and an EMPTY composer,
  the composer was 204px past the edge and the hint strip 246px, so the send button and every
  shortcut were gone with no draft involved, and focusing the field then scrolled the panel's own
  clipped box 247px and took the header off the top of it. **And it is worse on a bigger screen,**
  the caps being viewport fractions where the ceiling is not: 450px of hint strip outside at
  640x1400, 322px at 640x1000. It is a PAIR and not a family, which is the other thing worth
  checking: the stylesheet's other two `vh` caps (`.thoughts-body`, `.confirm-draft`) are inside
  the scrolling history, and with the switcher at its budgeted 227px and an approval draft at its
  full 302.39px in a 46px history the hint strip still cleared the edge by 1px.
- The fix is one number and one reservation. `overlay/panelBudget.ts` publishes the panel's
  ceiling as `--ceiling` beside the `max-height` it always equals, and overlay.css takes the
  column's own furniture off it (`--reserved`: the hairline, the header, the history's padding,
  the composer's margins around `--pill-floor`, the hint strip) and splits what is left between
  the two sections four sevenths to three, which is the 40 and the 30 they were already written
  in, read as shares. **The composer and the hint strip cannot lose because they are never in the
  budget.** A section alone with the panel still has all of it, so the ordinary case is
  bit-identical. After, at 640x720 with a seed of twelve chats and eleven reminders: the hint
  strip clears the edge by 1px and the composer by 43px in all five states this entry names,
  where they read 246/204 with both sections open, 282/240 with a draft at the field's ceiling,
  24/-18 with the switcher alone and 60/18 with the switcher alone under that draft. Mutated
  three ways and restored: the bare `vh` caps put 246 and 204 straight back, and taking
  `var(--pill-floor)` out of the reserve alone puts the hint strip 46.98px out with an empty
  composer, which is what proves the reservation rather than the cap is the half that keeps the
  composer on screen.

## Trail

- 2026-07-20: Measured with the panel's ceiling overridden to 300px and filed as a corner needing a
  full list, a full stack and a draft at the field's ceiling all at once.
- 2026-08-03: Landed as the neighbour-aware cap it asked for, with three of its own claims corrected
  upward. It is not a corner, the demo's own seed putting the hint strip 29.75px outside the moment
  the switcher opens; it is not bounded at the hint strip, the composer reading 204px outside with
  an empty field; and it is worse on a bigger screen, the caps being viewport fractions where the
  ceiling is not. Two bounds were opened behind it.
