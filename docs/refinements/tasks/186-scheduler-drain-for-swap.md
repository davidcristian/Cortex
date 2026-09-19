# `SubagentScheduler.drain()` for a swap

**Status:** done 2026-07-17
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

The subagent pool has to be quiet while the brain model is loaded and swapped back. It shipped as
`drain(*, timeout_s) -> bool` plus its reversal `undrain()` on the port, implemented by
`ResourceBudgetScheduler` and the new `AdmitAllScheduler` fake under one contract suite, composed
with `release`/`acquire` at the swap orchestrator without merging the ports.

The semantics the one-line plan could not state: entering the drain refuses every `admit` (typed
`SubagentAdmissionError`, `POOL_DRAINING_MSG`) instead of queuing, since a brain-phase spawn queued
against its own drain would deadlock the turn against its own swap; a spawn already waiting on a
full budget is woken and refused rather than left asleep through the handoff; the wait for in-flight
admissions is bounded by the timeout the conductor passes
(`CORTEX_SWAP_DRAIN_TIMEOUT_S`, default 60 s) and a timeout reports not-clean with nothing killed,
so the swap aborts before anything is evicted; and the window stays until `undrain`, which the
conductor owes in a `finally` on swap-back and abort alike.

## History

- 2026-07-15: Extracted from the roadmap's deferred-refinements section, one of this area's three
  entries blocked on the Slice 11 lifecycle.
- 2026-07-17: Closed with the brain-handoff drain sub-slice, whose semantics
  [ADR-0030](../../adr/ADR-0030-brain-handoff.md) decision 4 designed, and recorded at
  [ADR-0012 decision 10](../../adr/ADR-0012-resource-governance.md). The interleaving was proven by
  mutation, and the drain-resolves-on-release path was also watched live around a real streaming
  generation on the compose CPU `llama-server`.
- 2026-07-17: One text fix followed. The runner's wrapper called every admission refusal a permanent
  misconfiguration, which is false once a transient drain window exists, so the cause-specific
  guidance moved into each raise site's message.
- 2026-07-17: Recorded as a deliberate divergence from the admission wall, which queues when the
  budget is transiently full where the drain window refuses.
