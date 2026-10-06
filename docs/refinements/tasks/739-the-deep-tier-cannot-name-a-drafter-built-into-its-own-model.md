# The deep tier cannot name a drafter built into its own model

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** a Qwen3.8 artifact or a file under `Qwen3.6-27B-MTP-GGUF` named in
`CORTEX_MODEL_FILE_BRAIN` by a compose default, a recipe or an env file in this tree, or ADR-0004
decision 8 naming Qwen3.8-27B as the deep pick or its alternate. Read it with
`grep -rn 'CORTEX_MODEL_FILE_BRAIN' docker/ justfile` and decision 8's first sentence.
**Verified:** 2026-10-07

`drafter_flags` in `tiers.py` returns `--model-draft PATH --spec-type draft-mtp` for a named
`CORTEX_MODEL_FILE_BRAIN_DRAFT` and nothing otherwise (ADR-0004 decision 14), because the pick's
drafter is a file of its own. Qwen3.8-27B keeps its multi-token-prediction layer inside its own GGUF
(`blk.64`, `qwen35.nextn_predict_layers` 1), and the engine drafts with it on `--spec-type draft-mtp`
with no `--model-draft`; naming the model's own file as the drafter would load the whole model a
second time, which was read from the engine source and not run.

Measured 2026-09-26 ([deep candidates](../../readings/deep-candidates.md)): 1.40 to 1.43 times the
plain rate on reasoning and tool-call turns and 1.16 times on answer text, for 952 to 954 MiB more
on the card, at the 8192 context the deep tier then started at. Not drawn: the pick with its own
drafter on the same day, so the two drafters compare only across a week, and the
`Qwen3.6-27B-MTP-GGUF` variant of the alternate on the mount. That variant keeps the layer in its
own file too (`blk.64`, `qwen35.nextn_predict_layers` 1, where the plain `Qwen3.6-27B-GGUF` file
ends at `blk.63` with no such key), so the same fix serves the documented alternate; whether the
engine drafts with it was not run.

A fix lets the tier emit the type without a file, keeping `scripts/hostedtiers.py`'s single splat
and the roster test's reading of the brain argv, and a deployment using it measures
`CORTEX_SWAP_BRAIN_VRAM_MIB` and the decode minimum again with the layer drafting, as decision 14
asks of the pick's drafter.

## History

- 2026-09-26: filed by the deep candidates' measurement.
- 2026-09-30: not fired: `CORTEX_MODEL_FILE_BRAIN` defaults to empty in
  `docker/docker-compose.gpu.yml:71`, the justfile names no artifact, and ADR-0004 decision 8 names
  gemma-4-31B and Qwen3.6-27B. The deep tier now starts at 16384, so the body marks the drafting
  layer's cost as read at 8192; the fix's own re-measure of `CORTEX_SWAP_BRAIN_VRAM_MIB` covers it.
- 2026-10-04: not fired: `CORTEX_MODEL_FILE_BRAIN` still defaults to empty in
  `docker/docker-compose.gpu.yml:71`, the justfile and the tree hold no env file naming it, and
  decision 8 is unchanged. Read from the GGUF headers: the alternate's MTP variant holds the layer
  in its own file as Qwen3.8-27B does, so the trigger now names that variant too. The model host's
  b11312 build still lists `draft-mtp` among `--spec-type` values.
