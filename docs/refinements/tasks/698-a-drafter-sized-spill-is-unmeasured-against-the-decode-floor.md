# A drafter-sized spill is unmeasured against the decode floor

**Status:** done 2026-09-22
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

No guard was built for a co-resident deployment that names `CORTEX_MODEL_FILE_BRAIN_DRAFT` without
raising `CORTEX_SWAP_BRAIN_VRAM_MIB`. Such a deployment passes its fit check and loads about
1000 MiB more than it declared, and the only check that can see that afterwards is the spill watch,
which compares a handoff's best decode rate against `CORTEX_SWAP_BRAIN_DECODE_TPS` (`cadence.py`).

The model-swap runbook tells a deployment naming the drafter to measure that floor again with the
drafter drafting, because a floor taken on the plain tier sits further below a drafting tier's rate.
Whether that restores the watch is not known. The one spill this repo has read, in the runbook's
co-residency table, was 4676 MiB short and ran at 0.44 to 0.69 of the healthy rate. An overcommit no
larger than the drafter is at most about a fifth of that, and on this card, where the deep model and
the E4B tier leave about 908 MiB free, it would be about a tenth of the drafter. Nothing has read
how much an overcommit that small slows the deep tier, drafting or not.

**What would close it.** One run on the 24 GB card through Docker: the deep pick with its drafter
started beside the E4B subagent tier, with the free figure read before the load so the overcommit is
known, then a reasoning prompt and a tool-call turn timed against the same turns on the drafting
tier alone, with a card reading beside each rate. If the overcommitted rates fall below the drafting
tier's own floor, record that at ADR-0004 and close this as satisfied by the runbook step. If they
do not, the watch cannot see this overcommit, and the entry is restated with that reading and a fix
that does not rest on decode.

## History

- 2026-09-19: opened by the decision to cover the co-resident drafter case with the spill watch
  rather than a refusal, whose floor had never been read against an overcommit that small (the
  [ADR-0004](../../adr/ADR-0004-model-lineup.md) drafter recommendation).
- 2026-09-22: done by one run on the card. The drafting deep tier started beside the E4B tier, 917
  to 941 MiB short by the free figure (the E4B tier costs 3294 to 3307 MiB, not the 2878 read in
  August, so the overcommit was nearly the whole drafter rather than a tenth of it), decoded at 0.79
  of its solo rate on a reasoning prompt and 0.80 on a tool call. Against the slowest healthy
  drafting completion the watch sees the tool call (0.82 of it) and misses the reasoning trace
  (1.02), and a plain floor misses both, so the runbook step does not restore the watch. The
  readings are in [co-residency](../../readings/co-residency.md). The fix that does not rest on
  decode is [R-709](709-the-fit-check-does-not-count-the-deep-tiers-drafter.md). The E4B pair itself
  spilled in the same run, so the [model-swap](../../runbooks/model-swap.md) runbook leaves
  co-residency off on a 24 GB card, and the margin its fit figure needs is
  [R-710](710-the-free-memory-the-deep-tier-needs-beside-a-peer-is-unmeasured.md).
