# The engine budget's deep row voids on draws that think to the cap

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-07 by the close of
[R-590](590-two-renderings-laundering-cells-have-five-draws-an-arm.md), whose deep row runs once
per per-image token budget and drew clean at one of them.

The image arm sends no `max_tokens`, because the shipped request carries none and a cap this
harness invented would bound a reply the real path never bounds. The cortex tier deliberates on
purpose, so every draw of the arm is a thinking-on draw. At the shipped budget that costs nothing:
a draw generates 100 to 300 tokens and the deep row's 720 replies drew in 1078.92 s with none empty
or capped. At the engine's own budget, with the same screen resampled to 266 image tokens instead
of 629, a draw generates 600 to 1000, and three of `plain`'s 120 framed draws filled the whole
16384-token slot and came back with an empty `content`, the first of them 15181 tokens in 201.70 s.
That is the shape ADR-0005's void-row addendum names: a model that spends its budget thinking
returns a reply every detector scores as resistance. `Reply.unusable` reads each as a void draw and
`assert_drawn` reads the row as void, so the engine budget's half of the deep row costs about two
hours and then discards itself. The sitting stopped it after one rendering, 2537.44 s in, and hand
tallied that one: `plain` framed 37 of 120 obeyed against 119 of 120 in the control. `chrome` and
`app` have five draws an arm there.

**Why it was left.** The sitting's time box arrived first, and the fix is a decision rather than a
line: a cap the shipped path does not send would make the arm measure a request nobody makes, while
no cap leaves a two-hour row three long deliberations away from being void.

**What would close it.** Decide what a vision row does with a draw that thinks to the end of its
slot and land it: a cap declared and recorded as a departure from the request the brain sends, a
per-draw retry, or a row that reports the void draws and scores the rest. Then draw
`-k "drawn_deep and 12B and engine-budget"` to completion, which is about two hours of card time at
the rate this budget's replies run at. The three cells it would report are the ones the entry that
opened it asked for, read at the budget where both of them are known to apply the rule.

## Trail

- 2026-09-07: opened by the close of
  [R-590](590-two-renderings-laundering-cells-have-five-draws-an-arm.md), whose
  [ADR-0029 depth-at-both-budgets addendum](../../adr/ADR-0029-vision-screen-capture.md) records
  what the engine budget's replies cost and the reply that ran to the slot's end.
- 2026-09-08: **a second row at this budget voided, and its counts survived the void.** The deep
  row at `4800x2700` drew 1 empty reply in 240, so `assert_drawn` failed it and it reports as red.
  Its counts were still readable, because the void fell in the framed arm and the reading does not
  turn on the denominator: 56 of 120 and 56 of 119 are the same answer. One void in 240 against the
  three in 240 the corpus frame drew is one chance in three of being one rate drawn twice, so
  nothing here says a frame changes how often a draw thinks to the cap. What the two rows do say is
  that this budget voids on the order of one draw in a hundred, which is a row lost every time one
  is drawn. The rows are the
  [ADR-0029 two-pre-registered-rows addendum](../../adr/ADR-0029-vision-screen-capture.md).
