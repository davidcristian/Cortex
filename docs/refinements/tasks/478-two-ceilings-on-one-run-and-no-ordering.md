# Two ceilings bound one delegated run and nothing puts them in the same unit

**Status:** satisfied 2026-08-29
**Area:** subagents
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-28 by the close of
[R-457](457-the-caps-derivation-on-the-shape-that-ships.md), whose second question was which of a
run's bounds binds and whose answer is that it depends on how busy the host is.

The brain already fails at boot on three broken orderings around a delegated run:
`SubagentsConfig` checks the run deadline against the stall ceiling and the whole hold against the
admission wait, and `cortex_orchestrator.bounds` checks one stalled tool dispatch against the run
that has to contain it. Every one of those is a comparison between two **times**. The fourth
relation in the same family is between a time and a count, `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` against
`DEFAULT_SUBAGENT_MAX_TOKENS`, and nothing compares them because the exchange rate between them is
the tier's decode rate, which none of those modules can see.

Put in one unit at the shipped numbers, they are not consistent. At this tier's measured 0.18 to
1.35 tok/s, a 2400 s deadline admits about **425** decoded tokens on a saturated host and about
**3200** on an idle one, against a cap of 1024. So on a busy box the cap is unreachable and a run
long enough to deserve it is cut by the clock instead, which reports the other bound's refusal: the
cortex is told the subtask ran out of time when what happened is that it ran out of time doing
something the deployment had already declared too long. On an idle box the cap fires first, exactly
as intended. The same deployment is on both sides of the inversion depending on what else the
machine is doing.

**Why it was left.** There is no defect today. Both bounds refuse, both refusals are honest about
which one fired, and the ADR-0005 ceilings addendum now records the arithmetic where an operator
retuning either will meet it. What is missing is anything that keeps the two consistent, and the
obvious shapes for it are all worse than the gap: a boot check would need a decode rate in the
config, which is a hardware fact in a place that holds none, and a runtime one would have to measure
the tier before it could refuse a deployment. The three checks that do exist got away without one
because seconds compare to seconds.

**What would close it.** Most likely a decision rather than a check, recorded at
[ADR-0005](../../adr/ADR-0005-llamacpp-engine.md): either the two bounds are declared independent on
purpose, with the ceilings addendum's table as the operator's own conversion and a sentence saying
so beside both declarations, or one of them becomes derived from the other and a tier's rate becomes
a configured number rather than a measured one. Worth pricing before either: whether the refusal a
capped run returns and the refusal a deadline returns are distinguishable enough at the cortex for
the inversion to matter at all, since if the cortex narrows the subtask on both then the two bounds
differ only in what a human reads afterwards.

## Trail

- 2026-08-28: opened by the close of
  [R-457](457-the-caps-derivation-on-the-shape-that-ships.md), whose ceilings table put the two
  bounds in one unit and found the shipped pair inverted on a saturated host.
- 2026-08-29: Satisfied, on the first of the two resolutions it named, and the pricing question it
  asked is what chose between them. Answered from the code: the two refusals are distinguishable
  as **text and nowhere else**. One branch in the tree tells one failure kind from another
  (`SubagentRunner._placed`, which re-places only `INFERENCE` from a GPU placement), both
  truncations are the same `TRUNCATED` and neither is re-placed, the kind does not survive into
  `SubagentResult` (which carries `ok` and a `detail` string and no kind at all), and
  `SpawnSubagentsTool._format` renders a failed result as `FAILED: {detail}` and drops the
  fragment. The two sentences differ in their diagnosis and end in the same instruction, to treat
  the subtask as unanswered and narrow it. So the inversion cannot cause a wrong action, only a
  wrong diagnosis, and a documentation-shaped harm takes a documentation-shaped answer.
  **Two facts then made the ordering uncheckable rather than merely unchecked**, and the second is
  new here: which bound binds depends on what else the host is doing, worth a factor of seven on
  the overall decode rate and nineteen on the sustained one with nothing about the deployment
  changing, and on whether subagents hold tools, since the cap is spent per completion and the
  deadline armed once around the attempt, so a tools-enabled run may spend the cap on each of up to
  `MAX_TOOL_STEPS` rounds and the deadline binds at both ends of the measured range there. A
  validator has neither fact. **And deriving one from the other is wrong at one end of the same
  measured range either way**: a deadline derived from the cap at the slow end is a hold of about
  11460 s against a 7200 s admission wait, which the boot check that already exists rejects, and at
  the fast end it is about 772 s, under the 1736.6 s a legitimate narrow subtask was measured
  taking on a busy box; a cap derived from the deadline at the slow end is about 425 tokens, below
  the 429-token longest answer this tier has been measured writing. So the pair is declared
  independent on purpose in the ADR-0005 independence addendum, the conversion stays the operator's
  with the ceilings table as its instrument, and the sentence saying so is beside both declarations
  in `cortex_core/subagents.py`, in both module contracts, and in the delegation runbook.
  The entry's "no defect today" holds: both bounds refuse and both refusals name what fired.
  Opened by it: [R-494](494-one-pair-of-run-bounds-for-a-roster-of-tiers.md), since the decision
  hands the operator a conversion that is per tier and the config gives them one pair of bounds for
  the whole roster.
