# A spilled handoff is only ever in the log

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Opened 2026-08-18 by the close of [109](109-spill-does-not-latch.md), which declined the automatic
latch and left one half of that entry's trigger genuinely unanswered: the deployment whose operator
is not reading logs. The decode watch settles once per handoff and its whole consequence is a
`warning` record
([brain_phase.py](../../../brain/packages/core/src/cortex_core/brain_phase.py)); nothing else in
the process, and nothing at the seam, is any the wiser. A spill therefore looks exactly like a fit
to anyone who is not tailing the container.

The cheap surface already exists and is proven on a neighbouring fact. `StandingTiers.note_on`
annotates a **serving** residency report with a detail naming what is down
([residency_tiers.py](../../../brain/packages/core/src/cortex_core/residency_tiers.py)), `Health`
prefers that detail over its version string
([server.py](../../../brain/packages/orchestrator/src/cortex_orchestrator/server.py)), and the
overlay renders it in the indicator's tooltip with no overlay change at all. A spill verdict could
ride the same path, which would put "the last handoff spilled" in front of the one person who can
act on it.

What it costs, so the next reader does not mistake this for a one-line change: the deep phase holds
no reference to the manager that owns the residency record (the wiring hands it only the declared
decode rate), so this needs a writer the phase can reach, and that is a port question rather than a
read. It also needs a rule for how long such a note stands, since a spill is a fact about one
handoff while the tier record it would ride is a fact about now, and a note that never clears is a
second way to be wrong about the card. Re-derive both against the tree before starting.

## Trail

- 2026-08-18: Opened by the close of [109](109-spill-does-not-latch.md), which argued that the
  answer to an operator who does not read logs is to move the fact rather than to disable
  co-residency automatically.
