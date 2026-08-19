# A spill nobody was awake for is forgotten by design

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Trigger:** an operator asks whether a slow deep task has happened before, or a second
fact of this shape (a per handoff verdict worth counting rather than displaying) arrives
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Opened 2026-08-19 by the close of [304](304-spill-rides-the-residency-report.md). The standing
rule that close chose is deliberate and it has a price: the note lives in the process, stands for
an hour, and is cleared by the next handoff that holds its pace, so a handoff that spilled at
03:00 is gone by breakfast and a brain that restarted takes it with it. What an operator can read
is therefore only ever "the last handoff", never "this has happened four times this week", and the
log is the only place the history exists at all
([residency_pace.py](../../../brain/packages/core/src/cortex_core/residency_pace.py)).

That was the right trade for a display surface, since a report about **now** must not be
answered with a fact about last Tuesday. It is the wrong trade for a question about a pattern, and
the two want different homes: a count of spilled handoffs is durable data, not a tooltip, so
closing this means deciding where such a per handoff verdict is kept (the handoff record itself
already survives a swap and is already written per handoff) and what reads it, rather than
lengthening the note. Nothing about the current note changes either way.

## Trail

- 2026-08-19: Opened by the close of [304](304-spill-rides-the-residency-report.md), which argued
  the dwell from the two lifetimes a spill has and recorded, rather than smuggled, the history that
  choosing an hour throws away.
