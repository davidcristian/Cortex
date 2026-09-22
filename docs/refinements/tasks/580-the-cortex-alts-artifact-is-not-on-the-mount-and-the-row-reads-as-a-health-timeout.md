# The cortex alt's artifact is not on the mount and the row reads as a health timeout

**Status:** done 2026-09-06
**Area:** inference
**Origin:** [ADR-0060](../../adr/ADR-0060-injection-rows-follow-the-tier.md)

`MODELS` and `VISION_MODELS` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
name the cortex alt's weights `unsloth/Qwen3.5-9B-GGUF/Qwen3.5-9B-Q4_K_M.gguf`. That file is not on
this host's mount, which holds `Qwen3.5-9B-UD-Q4_K_XL.gguf`, `Qwen3.5-9B-Q8_0.gguf` and the
`mmproj-F32.gguf` the alt's image row uses. The server exits at once on
`load_model: failed to load model`, and because `_await_health` only polls `/health` the row waits
out the full 180 s timeout and fails as though the model were slow to load. Two attempts on
2026-09-06 read the same way, and the container's log is where the real reason is.

Two decisions sit behind the fix. Which quant the alt is measured as is a lineup identity: every
published alt count was drawn as `Q4_K_M`, and reading `UD-Q4_K_XL` under the same label would put
two quants in one column. And whether a server that exits should be reported as an exit rather than
as a timeout is a change to the harness's health wait, which every row shares.

## History

- 2026-09-06: opened by the close of
  [R-573](573-the-other-lineup-rows-have-no-obeyed-count-beside-their-mention-count.md), whose
  2026-09-06 lineup readings record the failed row
  ([injection text rows](../../readings/injection-text-rows.md)).
- 2026-09-06: done. The alt is measured as the `UD-Q4_K_XL` on the mount, where the candidate set
  named a `Q4_K_M` that is not there, and its rows stay in this repo rather than moving to
  `docs/host/`, since the card and the weights are both here. `_await_health` reads the container's
  state between polls and fails with the log tail, so the same row that spent 180 s now fails in
  3.47 s printing the load error. The alt's text row drew in 58.99 s at 1 of 10 framed obeyed
  against 4 of 10 unframed, which does not reproduce the published 0 of 10; the quant, the window
  and the command line all changed under it
  ([R-585](585-the-cortex-alts-framed-cell-has-one-measurement.md)), and the
  alt's image row is loadable and still undrawn
  ([R-586](586-the-cortex-alts-pixel-rows-are-undrawn-now-that-its-artifact-loads.md)). The
  2026-09-06 change of artifact ([ADR-0004](../../adr/ADR-0004-model-lineup.md)) records both
  decisions.
