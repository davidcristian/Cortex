# The window size sentence is unmeasured

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-24

Since 2026-09-24 the text beside a window capture says "downscaled from the window's WxH" or "at
the window's own size", from the reply's `target_width` and `target_height`. No draw has shown
whether that changes what the cortex reads. Two captions over a shrunk screen changed nothing:
offered "unreadable" as an answer, the cortex declined 3 of 47 strings and invented 38. So no change
is the expected result. The row that could show one is the 2400 px spreadsheet window of 2026-08-10
in [vision-capture](../../readings/vision-capture.md), which is wider than the edge and so
resampled.

`window_crop_probe.py` builds its captures with the target size, as the body does, unless
`messages()` is called with `sized=False`, which leaves both sizes at 0 as an older body would.
Its focus rows therefore include the sentence, so a redraw of them is not the input of the
2026-08-10 rows, and a comparison with them must say so.

## Pre-registered row

Written before any draw. `test_the_window_size_sentence_against_none` in
`test_image_budget_live.py` draws it.

- **Input.** The corpus's spreadsheet desktop, `focus` capture: the 2400x1350 window box filtered
  to 2048x1152 at the deployed edge (`DEFAULT_CAPTURE_MAX_EDGE`, 2048) and sent at the deployed
  image budget (`DEFAULT_IMAGE_MAX_TOKENS`, 1024), on the cortex tier's argv from
  `ModelHostConfig`. The `sized` side has the sentence, the `unsized` side does not; nothing else
  differs.
- **Sampler.** No `temperature` key, so the engine's own sampler as the cortex argv sets it, with
  `seed` 1 to 12 on both sides. Thinking is off (`enable_thinking: false`), as in the 2026-08-10
  rows, so the only output is the JSON answer.
- **Depth.** 12 seeds per side, 24 draws.
- **Deciding count.** Strings inside the window read per draw, of 9: the formula at 26 px, two
  column headers at 21 px, six cells at 20 px. The taskbar clock is outside the window and is not
  counted.
- **Test.** A two-sided exact sign test over the 12 seed pairs (sized count minus unsized count),
  ties dropped. p below 0.05 says the sentence changes what the cortex reads; otherwise the row
  found no change at this depth. A draw whose reply is not JSON is void and drops its pair; more
  than 2 void pairs voids the row.
- **Predictions, each with a 90% range.** Mean inside strings read per draw: unsized 3.0 to 6.5,
  sized 3.0 to 6.5. Mean paired difference, sized minus unsized: within 1.0 either way. The sign
  test finds no change (p at least 0.05). Void draws: 0 to 1 per side.
- **Price.** The 2026-08-10 window crop case took about 80 s for its 10 draws once the model was
  loaded ([inference measurements](../../runbooks/inference-measurements.md)), 8 s a draw at
  temperature 0. Sampled replies run longer, so a draw is priced at 2.5 times that, 20 s: 24 draws
  cost 8 min, plus up to 3 min for the corpus render and the server load. The test prints each
  draw's wall clock, and the log records the SM clock against its maximum.

## History

- 2026-09-24: Opened by the close of [R-253](253-reply-says-window-resampled.md), which added the
  sentence without a measurement.
