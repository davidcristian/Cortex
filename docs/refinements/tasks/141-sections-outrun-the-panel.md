# Two full sections outrun the panel

**Status:** done 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

`.switcher` may be `40vh` and `.reminders` `30vh`, each capped as if it were alone with the panel.
At the body's 720px window that is 504px of a 547px panel with the header (54px) and the hint
strip (33px) still to place. The composer yields down to one row of field plus its button row
before the panel's edge does ([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 19),
and the pill's 84px floor is where the yielding stops.

**Shipped 2026-08-03 as the neighbour-aware cap, and the entry understated itself three ways.**

- **It is not a corner.** On the demo's own seed of two chats and three reminders, at 640x720,
  pressing the switcher button once put the hint strip 29.75px past the panel's clipped edge and
  moved the composer 30.75px down. The 547 above is `openHeight(720)`, the ceiling of a panel
  held 86px off the bottom of the screen, and this state does not hold it there: on that seed the
  panel stands 450px tall on a 184px edge, and on a widened one 436px on a 198px edge. The entry's
  arithmetic was against a taller panel than the one the harm happens in.
- **It is not bounded at the hint strip.** With both sections at their caps and an empty composer,
  the composer was 204px past the edge and the hint strip 246px, so the send button and every
  shortcut were gone with no draft involved, and focusing the field then scrolled the panel's own
  clipped box 247px and took the header off the top of it.
- **It is worse on a bigger screen**, the caps being viewport fractions where the ceiling is not:
  450px of hint strip outside at 640x1400, 322px at 640x1000.

It is a pair and not a family. The stylesheet's other two `vh` caps (`.thoughts-body`,
`.confirm-draft`) are inside the scrolling history, and with the switcher at its budgeted 227px
and an approval draft at its full 302.39px in a 46px history the hint strip still cleared the edge
by 1px.

The fix is one number and one reservation. `overlay/panelBudget.ts` publishes the panel's ceiling
as `--ceiling` beside the `max-height` it always equals, and `overlay.css` takes the column's own
furniture off it (`--reserved`: the hairline, the header, the history's padding, the composer's
margins around `--pill-floor`, the hint strip) and splits what is left between the two sections
four sevenths to three, which is the 40 and the 30 they were already written in, read as shares.
The composer and the hint strip cannot lose, because they are never in the budget, and a section
alone with the panel still has all of it, so the ordinary case is unchanged.

After, at 640x720 with a seed of twelve chats and eleven reminders, the hint strip clears the edge
by 1px and the composer by 43px in all five states this entry names, where they read 246/204 with
both sections open, 282/240 with a draft at the field's ceiling, 24/-18 with the switcher alone
and 60/18 with the switcher alone under that draft. Mutated three ways and restored: the bare `vh`
caps put 246 and 204 straight back, and taking `var(--pill-floor)` out of the reserve alone puts
the hint strip 46.98px out with an empty composer, which shows that the reservation rather than
the cap is the half that keeps the composer on screen.

## History

- 2026-07-20: Measured with the panel's ceiling overridden to 300px and filed as a corner needing
  a full list, a full stack and a draft at the field's ceiling all at once.
- 2026-08-03: Shipped as the neighbour-aware cap, with three of its own claims corrected upward.
  Two further bounds were opened behind it ([R-142](142-budget-misses-section-frame.md) and
  [R-143](143-room-handed-back-in-one-frame.md)).
