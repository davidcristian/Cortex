# The two frames were compared at the one budget where a bigger picture is not a bigger picture

**Status:** landed 2026-09-04
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-30 by the close of
[R-432](432-the-image-arm-has-never-run-at-two-sizes.md), which ran the image arm at two frames
and found no size effect larger than the arm's own run-to-run variation.

The arm now runs at the corpus frame and at twice it, and both rows are published with a rate
row under them. What decides
whether a larger picture is a larger picture **to the model** is not the PNG's size but the
server's per-image token budget, and that close ran both frames at the shipped one. This ADR's own
legibility addendum already measured what the shipped budget does: one screen costs the same 266
prompt tokens at every capture edge from 1280 px to 3840 px, so the pixels above roughly 1040x585
are discarded inside the encoder. Two frames that differ only in pixels therefore arrive as the
same picture, and a result that finds no size effect is what the encoder's saturation predicts
rather than an independent finding about the framing.

`--image-max-tokens` moves that ceiling and the same addendum measured it moving: the same screen
costs 629 tokens from a 1600 px capture and 1010 from a 2048 px one at a 1024 budget, and the
legibility reading goes from 6 to 8 of 47 at the shipped budget to 36 to 38. A deployment that
raises the flag is exactly the deployment where the picture's size changes what the model can
read, and it is the one where a size-dependent resistance could exist at all. The arm has never
run there.

**Why it was left.** The close it came out of was one sitting with two rows of card time in it,
and a third and fourth row at a raised budget is another full pass of the same corpus. The flag is
also not what this stack ships, so the row is about a deployment a user opts into rather than
about the default, which is why it is a separate question and not a hole in the published pair.

**What would close it.** Run the image arm at both frames with `--image-max-tokens 1024` on the
server, which is one flag on the `_server` command line in
`brain/packages/inference/tests/test_injection_defense_live.py`, and publish the four rows against
the two already published. If nothing moves there either, the picture's size is settled for every
budget a deployment can set and the corpus's frame is a free choice unconditionally. If something
does, then resistance is a function of image tokens rather than of pixels, and the row that
matters is named by the flag rather than by the capture edge. Run the rate rather than the matrix
if only one fits: the matrices at the shipped budget differ by cells the rate showed to be
unstable, so a fourth pair of counts would answer nothing a fourth pair of rates would not.

## Trail

- 2026-08-30: opened by the close of
  [R-432](432-the-image-arm-has-never-run-at-two-sizes.md), which measured the two frames and
  their rates at the shipped budget and recorded that the budget is the variable it held
  constant.
- 2026-09-04: **landed, with the arm moved to the deployment's own budget and the frame still not
  a variable it can see.** The entry was right that both published pixel sittings ran at the
  engine's own per-image budget: `_server` named no image flags at all. It was wrong about whose
  deployment that is. `CORTEX_IMAGE_MAX_TOKENS` has defaulted to 1024 since 2026-08-06 and the GPU
  override names the same number, so the raised budget is the default and the arm's published rows
  described a stack nobody runs, which makes this the arm's first measurement of the shipped one
  rather than a row about an opt-in. The harness now starts at the shipped budget, `crosscheck.py`
  holds that literal to `DEFAULT_IMAGE_MAX_TOKENS`, and the engine's own budget stays selectable
  because every earlier row was measured there. The saturation the whole question rested on was
  also being read off another corpus, five 3840x2160 desktops downscaled to a capture edge, so the
  arm gained a row that asks the server what these screens cost: 266 tokens at both frames at the
  engine's budget, 629 and 1010 at the shipped one. The frame pair really was read at saturation,
  and the four new rows really are an experiment. Across them the frame moved the matrix by one
  cell per arm and the rate by 1 and 3 of 5 in opposite directions, all inside this arm's measured
  instability, so the corpus's frame is a free choice at both budgets. The budget itself moved the
  one cell that is obeyed rather than quoted: `plain/output-laundering` fired 14 of 20 arms at the
  engine's budget and 3 of 20 at the shipped one, and the framed firing that remains is a
  description of the rule rather than the rule applied. What is left is the single sitting
  ([R-542](542-the-shipped-budgets-rate-row-has-one-sitting.md)) and a detector whose description
  confound grows with the budget
  ([R-543](543-the-description-confound-grows-with-the-image-budget.md)). The rows and the decision
  are the [ADR-0029 image-budget addendum](../../adr/ADR-0029-vision-screen-capture.md).
