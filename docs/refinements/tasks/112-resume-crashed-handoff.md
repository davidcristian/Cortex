# Resume a crashed handoff from its record

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** the same dedup design the transport reconnect task needs, a request id plus an idempotency and resume registry keyed by it, after which resuming is a small addition to `recover_handoffs`.

Opened 2026-07-17 with the
brain-handoff conductor sub-slice ([ADR-0030](../../adr/ADR-0030-brain-handoff.md) decision 4),
which names it as the recorded refinement. Boot recovery marks any handoff a crash interrupted
`FAILED` and converges the GPU back onto the cortex; it deliberately does **not** re-run the
deep model's phase, even though the record holds everything needed to (that is the point of the
record). Replaying it would risk double-running side-effectful work, because nothing carries
request identity: the tail may contain tool calls whose results were fed back but whose effects
are not idempotent, and the deep phase's own dispatches would run again. Unlocked by the same
dedup design the seam-transport reconnect entry needs (a request id plus an
idempotency/resume registry keyed by it), after which resuming is a small addition to
`recover_handoffs`: read the record, re-enter the residency scope, and run `BrainPhase` against
it, which is exactly what the conductor already does. Until then the honest failure is the
cheaper one, and the user simply asks again.

## Trail

- 2026-07-17: Opened with the brain-handoff conductor sub-slice, which names it as its recorded
  refinement; the area went 3 to 4, one of three areas that each gained an entry from that
  sub-slice.
- 2026-07-19: Given a line in the index's pickup order, which it had lacked since it was written up,
  so that something said when to pick it up: it waits on the same request-identity and dedup design
  the `converse` reconnect entry needs, since replaying a deep phase without one risks
  double-running side-effectful tool work, after which resuming is a small addition to
  `recover_handoffs`.
