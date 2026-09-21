# No published comparison was drawn at the engine's sampler

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)
**Verified:** 2026-09-22

Every framed count in [injection over pixels](../../readings/injection-over-pixels.md) before
2026-09-22 was drawn at temperature 0 beside a control drawn the same way. There a control's prompt
is the same bytes in every draw and has one answer, while the framed count is a rate over the
fence's nonce, and up to 2026-09-19 the prompt cache also made a control's later draws a second
computation. So no published count compares two rates. ADR-0041's consequences that read a
direction from one rest on a one-answer control: the framing applying the rule at the shipped budget
where the control does not, the framing protecting only `chrome` at the engine budget, plain framed
at 4800x2700 against a silent control, and the alt's 9 of 280 on its plain cell. Eight draws per
condition at the engine's sampler on 2026-09-22 already read the `plain` control applying the rule
at both budgets.

The cells, in the order those consequences need them:

- the laundering cell at the corpus frame and size, all three renderings, at both budgets, pick;
- `plain` at 4800x2700 on the engine budget, pick;
- the alt's `plain` cell at the shipped budget;
- the five-draw and six-draw cells at the doubled and third frames, the payload-size table, the
  probe screens (`advisory`, `bare` and `chrome` at 16 px), the matrices, and the alt's other
  controls, among them the mail control that voids in every draw
  ([R-695](695-an-alt-mail-control-voids-in-every-draw-at-the-engine-budget.md)).

**What would close it.** Each listed cell drawn in both conditions with the rows as they now are,
which sample as the shipped request does and evaluate the whole prompt; the readings restated with
the new counts beside the temperature-0 ones, and ADR-0041's consequences edited where a direction
changes. A control count alone closes no cell, since the framed count beside it was drawn at
temperature 0. Every reply is read by hand, since a reply can apply the rule with its token misread
([R-707](707-a-misread-laundering-token-reads-as-resistance.md)).

## History

- 2026-09-22: opened by the close of
  [R-696](696-an-arms-first-draw-on-a-server-differs-from-the-rest.md), which found the prompt cache
  made a control's later draws a second computation and drew the corpus cells again whole.
