# The engine budget's deep row comes back empty on draws that think to the cap

**Status:** done 2026-09-08
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

The vision rows send no `max_tokens`, because the shipped request sends none and a cap this harness
invented would bound a reply the real path never bounds. The cortex tier deliberates deliberately,
so every draw is a thinking-on draw. At the shipped budget that costs nothing: a draw generates 100
to 300 tokens and the deep row's 720 replies drew in 1078.92 s with none empty or capped. At the
engine's own budget, with the same screen resampled to 266 image tokens instead of 629, a draw
generates 600 to 1000, and three of `plain`'s 120 framed draws filled the whole 16384-token slot and
came back with an empty `content`, the first of them 15181 tokens in 201.70 s. That is what ADR-0041
decision 14 names: a model that spends its budget thinking returns a reply every detector scores as
resistance. `Reply.unusable` reads each as a void draw and `assert_drawn` failed the whole row, so
the engine budget's half of the deep row costs about two hours and then discards itself. The session
stopped it after one rendering, 2537.44 s in, and hand tallied that one: `plain` framed 37 of 120
obeyed against 119 of 120 unframed.

## History

- 2026-09-07: opened by the close of
  [R-590](590-two-renderings-laundering-cells-have-five-draws-each.md), whose
  [ADR-0041 decision 16](../../adr/ADR-0041-injection-image-variant.md) records what the engine budget's
  replies cost and the reply that ran to the slot's end.
- 2026-09-08: a second row at this budget came back with a void draw, and its counts survived it.
  The deep row at `4800x2700` drew 1 empty reply in 240, so `assert_drawn` failed it. Its counts
  were still readable, because the void fell in the framed half and the reading does not turn on the
  denominator: 56 of 120 and 56 of 119 are the same answer. One void in 240 against the three in 240
  the corpus frame drew is one chance in three of being one rate drawn twice, so nothing says a
  frame changes how often a draw thinks to the cap. What the two rows do say is that this budget
  voids on the order of one draw in a hundred. The rows are
  [ADR-0041 decision 16](../../adr/ADR-0041-injection-image-variant.md).
- 2026-09-08: done, and the entry was right about the tree in every particular. A cap is refused
  because the vision rows claim to post the request the brain posts, and a per-draw retry is refused
  because it would redraw exactly the longest deliberations and keep the short ones, which biases
  the sample in a direction nothing here can sign. `assert_drawn` now takes the depth behind one
  reading, allows one void draw in twenty of that depth per reading named `cell:arm`, and prints the
  per-reading counts and the ceiling when a row has any; `rate` counts a void draw out of its
  denominator and names it, so a condition prints `56/119 (mentioned 78/119), 1 void of 120`; and
  `print_fired` marks a void draw rather than reading it. A row of distinct cells has a depth of one
  and a ceiling of zero, so both matrix rows and every text row keep the rule they have had since
  2026-09-05 and [R-575](575-one-void-reply-fails-a-row-that-drew-nineteen-cells.md) is untouched.
  Seven mutations of the harness were caught by the CI-side suite, and the two rows already drawn
  read again as 37 of 117 and 56 of 119 without either conclusion moving. The two-hour row this
  entry also asked for was not drawn and is opened as
  [R-613](613-the-engine-budgets-deep-row-is-drawn-for-one-rendering-of-three.md). The decision is
  [ADR-0041 decision 14](../../adr/ADR-0041-injection-image-variant.md).
