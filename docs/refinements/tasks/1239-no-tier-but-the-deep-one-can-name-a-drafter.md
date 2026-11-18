# No tier but the deep one can name a drafter

**Status:** done 2026-11-18
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

`CORTEX_MODEL_FILE_BRAIN_DRAFT` is the only drafter setting. `drafter_flags` in
`brain/packages/model_manager/src/cortex_model_manager/tiers.py` returns `--model-draft PATH
--spec-type draft-mtp` for it, and only the deep tier reads it (ADR-0004 decision 14). Since
2026-11-15 the models mount holds a drafter beside every gemma entry,
`unsloth/gemma-4-<size>-it-qat-GGUF/mtp-gemma-4-<size>-it-Q8_0.gguf` of architecture
`gemma4-assistant`, so the cortex and the GPU subagent tier have one on disk that no setting loads.

What the model cards say about drafters is in decision 5 of
[ADR-0077](../../adr/ADR-0077-model-card-settings.md), and none of it is measured here. Three
points decide the work:

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
- 2026-11-18: done. The premise held: only the deep tier read a drafter setting. The cortex and
  each GPU subagent server now start with the drafter beside their file at a draft length of 3,
  every tier has a drafter file and a draft length setting, and an empty file setting starts a
  tier without one ([ADR-0077](../../adr/ADR-0077-model-card-settings.md) decision 7). The remedy
  changed in two ways. The default follows the tier's file through a table in the model manager
  and is not a compose default, so another model is not started with a gemma drafter. And the
  gemma file drafts on two slots and with its projector, so a server of several slots loses its
  drafter only on a file the table does not list, with a warning at boot. The cortex file was
  drawn at 16K and the default stack was started on the card, with the projector and without it,
  at one slot and at two ([readings](../../readings/tier-drafters.md)). The cortex reservation
  went from 8.6 to 8.9 GiB, because the cortex with its projector and its drafter peaked 62 MiB
  over the old one. Not drawn: the rate with the projector loaded as a ratio, and the `Q4_0`
  drafter the cards name first, which the mount does not hold. Filed:
  [R-1246](1246-the-one-model-subagent-rows-read-higher-than-a-paired-reading.md) for two
  readings of one subagent server that differ. The CPU servers were drawn with the drafter and
  start without one (decision 7 of [ADR-0077](../../adr/ADR-0077-model-card-settings.md)).
