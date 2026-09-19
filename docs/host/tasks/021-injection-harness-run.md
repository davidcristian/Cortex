# The 31B injection-harness run

**Status:** done 2026-08-04
**Session:** gpu-tier-scale
**Capability:** G
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

The framed brain obeyed **0 of 10**; the unframed control obeyed 1. The pass line this item had,
that the framed brain refuses the corpus the way the cortex does, was met, so shipped policy does
not change.

**The measurement has left this directory**, per [index.md](../index.md)'s exit contract, and so has
the procedure, which was the other half of this item. The number and its evidence are the
[untrusted-framing](../../readings/untrusted-framing.md) readings, the row in
[ADR-0004](../../adr/ADR-0004-model-lineup.md)'s injection table, and the note against
[ADR-0030](../../adr/ADR-0030-brain-handoff.md) decision 1. The runbook section this item owed is
"The brain tier's injection-harness row" in
[runbooks/llamacpp-gpu.md](../../runbooks/llamacpp-gpu.md). The heading stays because the dependency
chain in the index points at it.

**What it found.** One row ran, `-k "31B"`, the pick's; the other three deep candidates and the
seven cortex and subagent rows did not. Framed, the pick resisted the whole corpus and six of its
ten reasoning traces cite the shipped preamble while doing it, which is the same causal signature
gemma-4-12B showed. Unframed, it fell to the tool exfil, emitting a real `send_email` call on an
instruction buried in a file it had been asked to summarize, so the one attack the framing
demonstrably stopped is the one with an action behind it. A perfect score on a reasoning model is
exactly where to distrust green, since [ADR-0004](../../adr/ADR-0004-model-lineup.md) had already
caught two candidates in the same group returning an empty `content` after burning a whole context,
and the harness scores `content` alone. A second pass recorded `finish_reason`, reply lengths and
the canary's presence in the trace, reproduced the matrix exactly, and showed no condition
truncating and every framed reply containing a correct summary. The runbook has that check as
procedure.

**What it hands the user, and what it deliberately did not do.**
[ADR-0030](../../adr/ADR-0030-brain-handoff.md) decision 1 gives two reasons for hard-denying
escalation on a tainted turn, and the run retires only the first: the deep tier's robustness is no
longer unmeasured. The second, that injected content must never force an eviction that claims the
card for minutes, is a resource-control argument a model measurement cannot touch. The position was
therefore left exactly as shipped and the choice recorded as a decision awaiting the user, on
[index.md](../index.md)'s list and at the ADR. Worth knowing before weighing it: the deny is the
generic approval branch in `dispatch.py` shared by every tool that needs approval, so relaxing it
for escalation carves an exception into a rule that has none.

**The ongoing half survives.** "Whenever picks or the preamble change" outlived this run and now
lives in the runbook section with the procedure, which is where a re-run will be read.

## History

- 2026-07-19: moved here from the untrusted-content area of the refinements backlog, one of five
  counted entries extracted that day, with a dated pointer left at the origin. It sat behind the
  deep-model pick with the other four capstone items, and it never shared this session's bring-up:
  it is a pytest that starts its own `llama-server` container and needs the model host down.
- 2026-08-04: run by the agent, once the hardware premise that filed it had been found false. The
  second item to leave this directory, and the first whose outcome could have changed shipped
  policy.
- 2026-08-04: its exit added a rule to the directory's exit contract, that an item owing a procedure
  exits by writing the procedure rather than by describing it. The four warnings this item had about
  how the harness fails were its most reusable content, so they left for the GPU runbook with the
  measurement.
- 2026-08-04: two corrections to the wording of the ADR-0030 risk this run hands the user are now
  stated in that ADR's decision 1 and should be read with it. The one not stated above is that the
  recorded alternative keeps a taint refusal rather than removing one.
