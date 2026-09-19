# Two limits bound one delegated run and nothing puts them in the same unit

**Status:** satisfied 2026-08-29
**Area:** subagents
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)

The brain already fails at boot on three broken orderings around a delegated run: `SubagentsConfig`
compares the run deadline with the stall limit and the whole wait with the admission wait, and
`cortex_orchestrator.bounds` compares one stalled tool dispatch with the run that has to contain it.
Each of those compares two times. The fourth relation in the same family is between a time and a
count, `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` against `DEFAULT_SUBAGENT_MAX_TOKENS`, and nothing compares
them because the conversion between them is the tier's decode rate, which none of those modules can
see.

Put in one unit at the shipped numbers, they are not consistent. At this tier's measured 0.18 to
1.35 tok/s, a 2400 s deadline admits about 425 decoded tokens on a busy host and about 3200 on an
idle one, against a cap of 1024. So on a busy box the cap is unreachable and the clock cuts the run
instead, reporting the other bound's refusal. On an idle box the cap fires first, as intended, and
the same deployment is on both sides of the inversion depending on what else the machine is doing.

## History

- 2026-08-28: opened by the close of
  [R-457](457-the-caps-derivation-on-the-shape-that-ships.md), whose table put the two bounds in one
  unit and found the shipped pair inverted on a busy host.
- 2026-08-29: satisfied, by declaring the two bounds independent, and the pricing question this
  entry asked is what chose that. The two refusals are distinguishable as text and nowhere else:
  one branch in the tree tells one failure kind from another (`SubagentRunner._placed`, which
  re-places only `INFERENCE` from a GPU placement), both truncations are the same `TRUNCATED` and
  neither is re-placed, the kind does not survive into `SubagentResult`, and
  `SpawnSubagentsTool._format` renders a failed result as `FAILED: {detail}`. The two sentences
  differ in their diagnosis and end in the same instruction, to treat the subtask as unanswered and
  narrow it, so the inversion cannot cause a wrong action, only a wrong diagnosis. Two facts then
  made the ordering impossible to check: which bound binds depends on what else the host is doing,
  worth a factor of seven on the overall decode rate and nineteen on the sustained one, and on
  whether subagents have tools, since the cap applies per completion and the deadline once around
  the attempt, so a tools-enabled run may spend the cap on each of up to `MAX_TOOL_STEPS` rounds. A
  validator has neither fact. Deriving one from the other is wrong at one end of the measured range
  either way: a deadline derived from the cap at the slow end is a wait of about 11460 s against a
  7200 s admission wait, which the existing boot check rejects, and at the fast end about 772 s,
  under the 1736.6 s a legitimate narrow subtask was measured taking on a busy box; a cap derived
  from the deadline at the slow end is about 425 tokens, below the 429-token longest answer this
  tier has been measured writing. So the pair is declared independent in ADR-0048, the conversion
  stays the operator's with the limits table as the instrument, and the sentence saying so is beside
  both declarations in `cortex_core/subagents.py`, in both module contracts, and in the delegation
  runbook. Opened by it: [R-494](494-one-pair-of-run-bounds-for-a-roster-of-tiers.md).
