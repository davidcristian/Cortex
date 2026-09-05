# The other four subagent candidates have no CPU row

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

Opened 2026-09-05 by the close of
[R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which gave the
injection harness a CPU placement and drew it for the pick alone.

`PLACEMENTS` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
gives every thinking-off model a `shipped-argv` row on the CPU, so gemma-4-E2B, Qwen3.5-0.8B,
Qwen3.5-2B and Qwen3.5-4B each collect one, and none has been run. The ADR-0004 placement-row
addendum's table has the pick's CPU row and nothing else's, so the injection table's claim that the
lineup was measured under one shape is true of the card alone.

**Why it was left.** A CPU row costs about half an hour on this host (the pick's cost 1837 s under
the stack's quota, twenty completions at under a token a second), so the four rows are two hours of
sitting for a comparison the pick's row already answers in kind: the framed arm did not move between
placements and the one cell that did was the corpus's unstable one. The roster alternate,
Qwen3.5-2B, is the one whose CPU row has a deployment behind it, since the roster override starts
it on the CPU.

**What would close it.** One sitting of `-k "cpu"` with the pick deselected, published in the same
table, and a reading of whether any candidate's framed count moved between placements by more than
the unstable cell.

## Trail

- 2026-09-05: opened by the close of
  [R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which drew
  the pick's CPU row twice and no other.
