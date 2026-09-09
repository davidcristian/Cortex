# Resume a crashed handoff from its record

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-09-09
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

**Re-derived on 2026-09-09 against the supervisor and the record, and the mechanism has not
moved.** `recover_handoffs`
([swap_recovery.py](../../../brain/packages/core/src/cortex_core/swap_recovery.py)) still does the
two things this entry describes and only those, failing the stranded record and converging
residency, and the module's own docstring gives the same reason for not resuming that this entry
gives. The claim this entry rests on is the one that bears on the rule that state must survive a
model swap, and it holds: `HandoffRecord`
([handoff.py](../../../brain/packages/core/src/cortex_core/handoff.py)) carries the brief, the
fence nonce, the whole taint ledger, the turn-wide dispatch budget's position, the rounds already
spent and the loop tail in order, which is everything a deep phase would need to be re-entered.
Resume is blocked by what the record deliberately does **not** carry, request identity, and not by
anything missing from the turn state. Nothing in the brain's source spells an idempotency key or a
request id today, and `CORTEX_ESCALATION` appears in `docker/` only inside a comment
(`docker-compose.gpu.yml`), so no deployment here can strand a handoff in the first place.

## Trail

- 2026-07-17: Opened with the brain-handoff conductor sub-slice, which names it as its recorded
  refinement; the area went 3 to 4, one of three areas that each gained an entry from that
  sub-slice.
- 2026-07-19: Given a line in the index's pickup order, which it had lacked since it was written up,
  so that something said when to pick it up: it waits on the same request-identity and dedup design
  the `converse` reconnect entry needs, since replaying a deep phase without one risks
  double-running side-effectful tool work, after which resuming is a small addition to
  `recover_handoffs`.
- 2026-09-09: claims held to the code, and the account of the handoff re-derived from the
  supervisor and the record rather than spot-checked. Nothing has been restructured: boot recovery
  fails the stranded record and converges, the record still holds every part of the turn a resume
  would replay, and the dedup design that would unlock it exists nowhere in the brain's source. The
  trigger has not fired.
