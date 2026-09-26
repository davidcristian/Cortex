# A Qwen3.8-27B deep tier has no measured fit figure or decode floor

**Status:** open, waiting for its trigger
**Area:** resource-governance
**Origin:** [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md)
**Trigger:** a Qwen3.8 artifact named in `CORTEX_MODEL_FILE_BRAIN` by a compose default, a recipe
or an env file in this tree, or ADR-0004 decision 8 naming Qwen3.8-27B as the deep pick or its
alternate. Read it with `grep -rn 'CORTEX_MODEL_FILE_BRAIN' docker/ justfile` and decision 8's
first sentence.
**Verified:** 2026-09-26

A deployment declares the deep tier's cost in `CORTEX_SWAP_BRAIN_VRAM_MIB`, the figure the fit check
compares free memory against, and its spill-watch minimum in `CORTEX_SWAP_BRAIN_DECODE_TPS`. The
model-swap runbooks give both for the pick: a cost of 19125 MiB and a declared 20125, set above the
highest free figure at which the pick spilled beside a filler (19967 MiB,
[co-residency](../../readings/co-residency.md)). For Qwen3.8-27B only the cost was read, 15,744 to
15,770 MiB above the idle card plain and 16,703 to 16,705 with its own prediction layer drafting
(2026-09-26, [deep candidates](../../readings/deep-candidates.md)). Where it spills, and its decode
minimum from a cold load onto a clear card, were not drawn.

The same reading bears on two settings that follow from the pick's figures. Beside the idle GPU
subagent tier the card had 19,866 and 19,874 MiB free before a deep load (2026-09-22), about 4,100
MiB above Qwen3.8-27B's cost, where the pick with about 750 MiB spare spilled; co-residency
([ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md) decision 1) may hold for it where it
does not for the pick. And the deep tier's `--cache-ram 0` rests on the pick's 3.5 GiB a cached
conversation ([ADR-0059](../../adr/ADR-0059-prompt-cache-per-tier.md) decision 4); the hybrid
model's attention cache costs 64 KiB a token, so a cached conversation may cost a fraction of that.

What would close it: the margin draw of `measurements/deep-margin-2026-09-22/draw.py` with the rule
of the pick's row, the decode floor from `test_decode_cadence_live.py`, and the prompt-cache row of
`measurements/cache-ram-tiers-2026-09-13/`, each on Qwen3.8-27B at the deep tier's argv.

## History

- 2026-09-26: filed by the deep candidates' measurement.
