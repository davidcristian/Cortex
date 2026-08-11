# `SubagentScheduler.drain()` for a swap

**Status:** landed 2026-07-17
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

The entry read: "Quiesce
the subagent pool (evict → load brain → swap back). An additive method delivered in **Slice
11**, composed with `release`/`acquire` at the swap orchestrator, never merging the ports."
It landed exactly there: `drain(*, timeout_s) -> bool` plus its reversal `undrain()` on the
port, implemented by `ResourceBudgetScheduler` and the new `AdmitAllScheduler` fake under one
contract suite. The semantics the original one-liner could not carry: entering drain refuses
every `admit` (typed `SubagentAdmissionError`, `POOL_DRAINING_MSG`) instead of queuing, since
a brain-phase spawn queued against its own drain would deadlock the turn against its own swap;
a spawn already waiting on a full budget is woken and refused, not left to sleep through the
handoff; the wait for in-flight admissions is bounded by the conductor-passed timeout
(`CORTEX_SWAP_DRAIN_TIMEOUT_S`, default 60 s, arriving with the conductor's wiring) and a
timeout reports not-clean with nothing killed, so the swap aborts before anything is evicted;
and the window holds until `undrain`, which the conductor owes in a `finally` on swap-back and
abort alike. The swap conductor that calls it is the ADR-0030 conductor sub-slice, which
consumes this verb as landed.

## Trail

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section, one of this area's three
  entries blocked on the Slice 11 lifecycle.
- 2026-07-17: Landed with the brain-handoff drain sub-slice, whose semantics
  [ADR-0030](../../adr/ADR-0030-brain-handoff.md) decision 4 designed, and recorded at the
  [ADR-0012 drain addendum](../../adr/ADR-0012-resource-governance.md). It landed as the entry said, an
  additive port method composed at the swap orchestrator, plus the reversal verb the entry never
  named. The crux interleaving was mutation-proven, and the drain-resolves-on-release path was also
  observed live around a real streaming generation on the compose CPU `llama-server`.
- 2026-07-17: The refusal riding the existing typed `SubagentAdmissionError` surfaced one text fix.
  The runner's wrapper called every admission refusal a permanent misconfiguration, which is false
  once a transient drain window exists, so the cause-specific guidance moved into each raise site's
  message.
- 2026-07-17: Recorded as the first of this area's three entries blocked on the Slice 11 lifecycle to
  clear, its blocker being built at the time, and as a deliberate divergence from the admission
  wall's queue-on-transient-fullness philosophy, since the drain window refuses where a transiently
  full budget queues.
