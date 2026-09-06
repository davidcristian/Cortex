# The cortex alt's artifact is not on the mount and the row reads as a health timeout

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

Opened 2026-09-06 by the close of
[R-573](573-the-other-lineup-rows-have-no-obeyed-count-beside-their-mention-count.md), whose
sitting drew four of its five rows.

`MODELS` and `VISION_MODELS` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
name the cortex alt's weights `unsloth/Qwen3.5-9B-GGUF/Qwen3.5-9B-Q4_K_M.gguf`. That file is not on
this host's mount, which holds `Qwen3.5-9B-UD-Q4_K_XL.gguf`, `Qwen3.5-9B-Q8_0.gguf` and the
`mmproj-F32.gguf` the image arm's alt row uses. The server exits at once on `load_model: failed to
load model`, and because `_await_health` only polls `/health` the row spends the full 180 s
timeout and fails as though the model were slow to load. Two attempts on 2026-09-06 read the same
way, and the container's log is where the real reason is.

**Why it was left.** Two decisions sit behind the fix and neither belongs in a sitting's writeup.
Which quant the alt is measured as is a lineup identity: every published alt count was drawn as
`Q4_K_M`, and reading `UD-Q4_K_XL` under the same label would put two quants in one column. And
whether a server that exits should be reported as an exit rather than as a timeout is a change to
the harness's health wait, which every row shares.

**What would close it.** Decide the artifact first: either name the quant that is on the mount and
say in the lineup table that the alt's rows from that date are a different quant, or record the
`Q4_K_M` as an artifact this host does not hold and move the alt's rows to `docs/host/`. Then make
`_await_health` fail on a container that has exited rather than waiting out the timeout, so a
missing or broken artifact reports itself. Both the text arm's alt row and the image arm's are
blocked on the first half.

## Trail

- 2026-09-06: opened by the close of
  [R-573](573-the-other-lineup-rows-have-no-obeyed-count-beside-their-mention-count.md), whose
  [ADR-0004 lineup-readings addendum](../../adr/ADR-0004-model-lineup.md) records the failed row.
