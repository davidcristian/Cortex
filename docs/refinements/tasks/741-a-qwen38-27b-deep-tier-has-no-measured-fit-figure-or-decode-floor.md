# A Qwen3.8-27B deep tier has no measured fit figure or decode floor

**Status:** open, actionable
**Area:** resource-governance
**Origin:** [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md)
**Verified:** 2026-11-20

A deployment declares the deep tier's cost in `CORTEX_SWAP_BRAIN_VRAM_MIB`, the figure the fit check
compares free memory against, and its spill-watch minimum in `CORTEX_SWAP_BRAIN_DECODE_TPS`. The
[model-swap](../../runbooks/model-swap.md) runbook gives gemma-4-31B's cost at the shipped 16384
context as 664 to 667 MiB more than 8192 and declares 20783; at 8192 it cost 19125 and 20125 was set
above the highest free figure at which it spilled beside a filler (19967 MiB,
[co-residency](../../readings/co-residency.md)). For Qwen3.8-27B only the cost was read: at 8192,
15,744 to 15,770 MiB above the idle card plain and 16,703 to 16,705 with its own prediction layer
drafting, and at 16384 16,273 plain (2026-09-26,
[deep candidates](../../readings/deep-candidates.md)). Where it spills, and its decode minimum from
a cold load onto a clear card, were not drawn.

The same reading bears on two settings that follow from gemma-4-31B's figures. Beside the idle GPU
subagent tier the card had 19,866 and 19,874 MiB free before a deep load (2026-09-22), about 3,600
MiB above Qwen3.8-27B's cost at 16384, where gemma-4-31B at 8192 spilled with about 750 MiB spare;
co-residency ([ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md) decision 1) may hold
for it where it does not for gemma-4-31B. And the deep tier's `--cache-ram 0` rests on gemma-4-31B's 3.5
GiB a cached conversation ([ADR-0059](../../adr/ADR-0059-prompt-cache-per-tier.md) decision 4);
the hybrid model's attention cache costs 64 KiB a token, so a cached conversation may cost a
fraction of that.

What would close it: the margin draw of `measurements/deep-margin-2026-09-22/draw.py` with the rule
of gemma-4-31B's row, the decode floor from `test_decode_cadence_live.py`, and the prompt-cache row of
`measurements/cache-ram-tiers-2026-09-13/`, each on Qwen3.8-27B at the deep tier's argv.

## History

- 2026-09-26: filed by the deep candidates' measurement.
- 2026-09-30: not fired: `CORTEX_MODEL_FILE_BRAIN` defaults to empty in
  `docker/docker-compose.gpu.yml:71`, the justfile names no artifact, and ADR-0004 decision 8 names
  gemma-4-31B and Qwen3.6-27B. The deep tier now starts at 16384, so the body gives the pick's
  figures at that context and Qwen3.8-27B's 16,273 MiB there, with the 8192 figures marked as such.
- 2026-10-04: not fired: `CORTEX_MODEL_FILE_BRAIN` still defaults to empty in
  `docker/docker-compose.gpu.yml:71`, the justfile names no artifact, and decision 8 is unchanged.
  The runbook's 19125, 20125, 20783 and 664 to 667 MiB, the co-residency 19967, 19866 and 19874
  MiB, the Qwen3.8-27B figures and the three measurement paths all stand. The `llmfan46/`
  Qwen3.8-27B repackage on the mount since 2026-09-30 is no candidate and does not fire it.
- 2026-10-25: checked again and not fired: `CORTEX_MODEL_FILE_BRAIN` still names no Qwen3.8 file;
  `scripts/switchlineup.py` lists one only for the thinking switch lineup.
- 2026-11-10: checked again and not fired: `CORTEX_MODEL_FILE_BRAIN` still defaults to empty, the
  justfile names no Qwen file, and decision 8 of ADR-0004 still picks gemma-4-31B.
- 2026-11-16: fired: ADR-0004 decision 8 names Qwen3.8-27B as the deep alternate, since the
  models mount no longer holds Qwen3.6-27B. None of the three draws named here was made.
- 2026-11-20: ADR-0004 decision 8 now names Qwen3.8-27B as the deep pick, so a deployment of the
  pick has no measured figure for `CORTEX_SWAP_BRAIN_VRAM_MIB` or `CORTEX_SWAP_BRAIN_DECODE_TPS`.
  One more cost was read since: 16,991 MiB above the floor at 16384 with `q8_0`, drafting at
  length 3 (R-1243's History, 2026-11-18). None of the three draws named here was made.
  Filed: [R-1268](1268-no-handoff-has-run-through-the-brain-on-qwen38-27b.md) for a handoff through the brain on this file.
