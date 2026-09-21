# Control counts away from the corpus cells were read from the cache

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)
**Verified:** 2026-09-22

Every control count in [injection over pixels](../../readings/injection-over-pixels.md) up to
2026-09-19 was drawn with the engine's prompt cache on. That makes a control count behind one load
two computations, and makes a cell's reading depend on the cells drawn before it on that server.
On 2026-09-22 the laundering control was drawn whole at the corpus frame and size for all three
renderings at both budgets, and `plain` at 16 px at the engine budget. Only `plain` at the engine
budget read differently: evaluated whole, it does not apply the rule. These have not been drawn
whole:

- the five-draw and six-draw cells at the doubled and third frames, where `plain`'s control read 0
  or 1 of 5 and `chrome`'s 5 of 5 at the engine budget;
- the payload-size table's controls at 16 and 8 px;
- the probe screens: `advisory` at 16 px (1 of 20 in one row, 19 of 20 in another), `bare`, and
  `chrome` at 16 px;
- the control columns of the matrices, one draw per cell, each evaluated from where the cell before
  it left the cache;
- the alt candidate's controls, among them the mail control that voids in every draw
  ([R-695](695-an-alt-mail-control-voids-in-every-draw-at-the-engine-budget.md)).

One consequence in ADR-0041 rests on them: at 4800x2700 on the engine budget, plain framed applies
about half the time "against a silent control".

**What would close it.** Each listed control cell drawn with the rows as they now are, which send
`cache_prompt: false`, so one draw is the cell's answer; the readings restated where a cell reads
differently, and ADR-0041's consequences edited where one rested on it. The rows as written draw a
control 5 to 560 times, so a row drawing each control cell once is the cheaper route.

## History

- 2026-09-22: opened by the close of
  [R-696](696-an-arms-first-draw-on-a-server-differs-from-the-rest.md), which found the cache made a
  control's later draws a second computation and drew the corpus cells again whole.
