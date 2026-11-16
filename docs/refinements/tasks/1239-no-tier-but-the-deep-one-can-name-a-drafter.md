# No tier but the deep one can name a drafter

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-16

`CORTEX_MODEL_FILE_BRAIN_DRAFT` is the only drafter setting. `drafter_flags` in
`brain/packages/model_manager/src/cortex_model_manager/tiers.py` returns `--model-draft PATH
--spec-type draft-mtp` for it, and only the deep tier reads it (ADR-0004 decision 14). Since
2026-11-15 the models mount holds a drafter beside every gemma entry,
`unsloth/gemma-4-<size>-it-qat-GGUF/mtp-gemma-4-<size>-it-Q8_0.gguf` of architecture
`gemma4-assistant`, so the cortex and the GPU subagent tier have one on disk that no setting loads.

What the model cards say about drafters, read 2026-11-16, is not measured here. Three points
decide the work:

- The gemma cards draft 4 tokens at a time. The model host passes no `--spec-draft-n-max`, and
  the engine's default is 3.
- The mount holds the `Q8_0` drafter, which is named by path, and the cards' default is a `Q4_0`.
- The Qwen cards say more than one slot and `--mmproj` are not supported with multi-token
  prediction. A subagent server runs two slots, and the cortex runs with its projector when
  vision is on. The gemma cards state neither limit.

What would close it: a draw of the cortex with its drafter at the tier's argv, with the projector
and without it, for rate, VRAM and whether a turn with a picture still answers; the same for the
GPU subagent tier at one slot and at two; then a drafter setting for each tier that gains, or the
reason written down for a tier that does not. A model with the layer in its own file is
[R-739](739-the-deep-tier-cannot-name-a-drafter-built-into-its-own-model.md).

## History

- 2026-11-16: filed when the lineup moved to the files the mount holds.
