# A spilled handoff is only ever in the log

**Status:** done 2026-08-19
**Area:** inference-model-manager
**Origin:** [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md)

Opened 2026-08-18 by the close of [109](109-spill-does-not-latch.md), which declined the automatic
latch and left one half of that entry's trigger unanswered: the deployment whose operator is not
reading logs. The decode watch decides once per handoff and its whole consequence is a `warning`
record ([brain_phase.py](../../../brain/packages/core/src/cortex_core/brain_phase.py)); nothing
else in the process, and nothing on the wire, records it. A spill therefore looks exactly like a
fit to anyone who is not tailing the container.

The cheap surface already exists and is proven on a neighbouring fact. `StandingTiers.note_on`
annotates a serving residency report with a detail naming what is down
([residency_tiers.py](../../../brain/packages/core/src/cortex_core/residency_tiers.py)), `Health`
prefers that detail over its version string
([server.py](../../../brain/packages/orchestrator/src/cortex_orchestrator/server.py)), and the
overlay renders it in the indicator's tooltip with no overlay change at all.

Two costs were named and both stood. The deep phase holds no residency (the wiring hands it the
declared decode rate and nothing else), so the writer is a port: `PaceSink`, one method, a result
and never a reading, synchronous because the phase calls it between its stream ending and its reply
being persisted. And a note needs a rule for how long it applies, since a spill is a fact about one
handoff while the tier record it joins is a fact about now. The record behind it is
[residency_pace.py](../../../brain/packages/core/src/cortex_core/residency_pace.py), held by the
manager beside the peer record and composed into a serving report as it is read. The rule is that a
later handoff decides the note in both directions and, failing one, it expires after an hour; the
two notes combine rather than compete, through one shared `with_note`, since a down peer and a
spilled handoff have different remedies. One cost the entry did not name turned up: `residency.py`
was one line under the cap, so the reporting surface moved out as `ResidencyProbeMixin`.

## History

- 2026-08-18: Opened by the close of [109](109-spill-does-not-latch.md), which argued that the
  answer to an operator who does not read logs is to move the fact rather than to disable
  co-residency automatically.
- 2026-08-18: One constraint recorded by the residency regain work beside this
  ([116](116-reconciliation-without-a-turn.md)), since it decides where the note may live. That
  pass republishes the bare `RESIDENCY_SERVING` constant whenever it finds the cortex back, so a
  detail written into the published record would be erased by it; use the read-time composition
  `StandingTiers.note_on` already does in `residency()` instead.
- 2026-08-19: Done. The result now travels on a serving residency report's detail and reads in the
  connection tooltip as "the last deep task ran far slower than this deployment measured for it, so
  deep tasks are taking much longer than they should", which names the consequence, because a
  tooltip's reader can act on lost time and not on a decode rate. Reasoning at
  [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md) decision 5; the seven mutations
  that prove it are in the headers of `test_residency_pace.py` and `test_brain_phase.py`. Two
  narrower entries came out of it: the display compromise a one-string detail field forces is
  [320](320-one-detail-string-two-facts.md), and the history the one-hour expiry throws away is
  [321](321-a-spill-nobody-saw-is-forgotten.md).
