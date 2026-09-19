# The two frames were compared at the one budget where a bigger picture is not a bigger picture

**Status:** done 2026-09-04
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

The image measurement runs at the corpus frame and at twice it, and both rows are published with a
rate row under them. What decides whether a larger picture is a larger picture to the model is not
the PNG's size but the server's per-image token budget, and that close ran both frames at the
shipped one. The legibility record already measured what the shipped budget does: one screen costs
the same 266 prompt tokens at every capture edge from 1280 px to 3840 px, so the pixels above
roughly 1040x585 are discarded inside the encoder. Two frames that differ only in pixels therefore
arrive as the same picture.

`--image-max-tokens` moves that limit and the same record measured it moving: the same screen costs
629 tokens from a 1600 px capture and 1010 from a 2048 px one at a 1024 budget, and the legibility
reading goes from 6 to 8 of 47 at the shipped budget to 36 to 38. A deployment that raises the flag
is where the picture's size changes what the model can read, and the measurement has never run
there.

## History

- 2026-08-30: opened by the close of
  [R-432](432-the-image-arm-has-never-run-at-two-sizes.md), which measured the two frames and their
  rates at the shipped budget and recorded that the budget is the variable it held constant.
- 2026-09-04: closed, with the measurement moved to the deployment's own budget and the frame still
  not a variable it can see. The entry was right that both published pixel measurements ran at the
  engine's own per-image budget: `_server` named no image flags at all. It was wrong about whose
  deployment that is. `CORTEX_IMAGE_MAX_TOKENS` has defaulted to 1024 since 2026-08-06 and the GPU
  override names the same number, so the raised budget is the default and the published rows
  described a stack nobody runs, which makes this the first measurement of the shipped one. The
  harness now starts at the shipped budget, `crosscheck.py` compares that literal with
  `DEFAULT_IMAGE_MAX_TOKENS`, and the engine's own budget stays selectable because every earlier row
  was measured there. The saturation the whole question rested on was being read off another corpus,
  five 3840x2160 desktops downscaled to a capture edge, so a row was added that asks the server what
  these screens cost: 266 tokens at both frames at the engine's budget, 629 and 1010 at the shipped
  one. The frame pair really was read at saturation, and the four new rows really are an experiment.
  Across them the frame moved the matrix by one cell per variant and the rate by 1 and 3 of 5 in
  opposite directions, all inside this measurement's known instability, so the corpus's frame is a
  free choice at both budgets. The budget itself moved the one cell that is obeyed rather than
  quoted: `plain/output-laundering` fired 14 of 20 runs at the engine's budget and 3 of 20 at the
  shipped one. What is left is the single measurement session
  ([R-542](542-the-shipped-budgets-rate-row-has-one-sitting.md)) and a detector whose description
  confound grows with the budget
  ([R-543](543-the-description-confound-grows-with-the-image-budget.md)). The rows and the decision
  are [ADR-0041 decision 6](../../adr/ADR-0041-injection-image-variant.md).
