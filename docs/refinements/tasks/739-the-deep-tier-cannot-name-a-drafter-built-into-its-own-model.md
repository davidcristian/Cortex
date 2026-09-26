# The deep tier cannot name a drafter built into its own model

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** a Qwen3.8 artifact named in `CORTEX_MODEL_FILE_BRAIN` by a compose default, a recipe
or an env file in this tree, or ADR-0004 decision 8 naming Qwen3.8-27B as the deep pick or its
alternate. Read it with `grep -rn 'CORTEX_MODEL_FILE_BRAIN' docker/ justfile` and decision 8's
first sentence.
**Verified:** 2026-09-26

`drafter_flags` in `tiers.py` returns `--model-draft PATH --spec-type draft-mtp` for a named
`CORTEX_MODEL_FILE_BRAIN_DRAFT` and nothing otherwise (ADR-0004 decision 14), because the pick's
drafter is a file of its own. Qwen3.8-27B keeps its multi-token-prediction layer inside its own GGUF
(`blk.64`, `qwen35.nextn_predict_layers` 1), and the engine drafts with it on `--spec-type draft-mtp`
with no `--model-draft`; naming the model's own file as the drafter would load the whole model a
second time, which was read from the engine source and not run.

Measured 2026-09-26 ([deep candidates](../../readings/deep-candidates.md)): 1.40 to 1.43 times the
plain rate on reasoning and tool-call turns and 1.16 times on answer text, for 952 to 954 MiB more
on the card. Not drawn: the pick with its own drafter on the same day, so the two drafters compare
only across a week, and the `Qwen3.6-27B-MTP-GGUF` variant of the alternate on the mount.

A fix lets the tier emit the type without a file, keeping `scripts/hostedtiers.py`'s single splat
and the roster test's reading of the brain argv, and a deployment using it measures
`CORTEX_SWAP_BRAIN_VRAM_MIB` and the decode minimum again with the layer drafting, as decision 14
asks of the pick's drafter.

## History

- 2026-09-26: filed by the deep candidates' measurement.
