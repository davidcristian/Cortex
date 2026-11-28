# The micro-batch test expects an abort the engine now turns into a cap

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-11-28

`test_a_raised_budget_without_the_micro_batch_aborts_the_server` in
`brain/packages/inference/tests/test_image_budget_live.py` starts the cortex tier's argv with
`--ubatch-size` removed and asserts that `llama-server` exits on a 4K screen. On build
`b12375-9d25e0014`, with `mmproj-F32.gguf`, the server stays up and the test fails. At load it logs
`cap image_max_tokens (original=1024) to 512 (n_ubatch = 512) because model needs non-causal
attention on image`, and a second start answered the 4K screen with HTTP 200 at 502 prompt tokens,
where the paired argv costs the same screen 1010
([vision capture](../../readings/vision-capture.md#image-tokens-and-the-budget)). So the pairing in
`image_budget_flags` (`cortex_model_manager/tiers.py`) is still needed, since without it the budget
falls to the micro-batch. What changed is the failure: a cap the log states, not an abort.

The fix rewrites the test to assert what the engine does now: the server survives and the screen
costs at most the 512-token micro-batch, an assertion the paired argv's 1010 fails. It also
corrects the text that says the budget alone aborts: decision 17 of ADR-0029, the
`--image-max-tokens` bullet of the [GPU runbook](../../runbooks/llamacpp-gpu.md), the abort
clause of [inference measurements](../../runbooks/inference-measurements.md), and the
`_ENGINE_UBATCH` comment in the test. Each of those three documents is at 250 lines.

## History

- 2026-11-28: filed by
  [R-1238](1238-the-lineups-readings-were-drawn-on-files-the-mount-no-longer-holds.md), whose draw
  of the two live image tests on the files the tier names found the server alive where this test
  expects an abort. The argv assert before it now finds the micro-batch pair wherever it is, since
  the drafter flags follow it.
