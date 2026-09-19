# Resume a crashed handoff from its record

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-09-19
**Trigger:** the dedup design the `Converse` reconnect entry (R-023) needs, a request id on `UserTurn` or `ClientEvent` plus an idempotency and resume registry keyed by it, after which resuming is a conductor entry point run beside the seam. Recheck with `grep -rniE 'request_id|idempotency' proto/body.proto brain/packages/*/src`: no hit means the design does not exist and this has not fired.

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
request id today. The paragraph said on 2026-09-09 that `CORTEX_ESCALATION` appeared in `docker/`
only inside a comment, so no deployment could strand a handoff; since 2026-09-17 the gpu overlay
passes it through by name, so a host `.env` can turn escalation on and a crash can strand a record,
while no shipped file sets it.

**Corrected 2026-09-19: the resume does not belong in `recover_handoffs`.** The composition root
awaits it in `recover_boot_residency` (`swap_builders.py`) before the seam serves its first turn,
so a deep phase run there would hold every turn off for a model load and a whole phase. The
sequence a resume needs is the conductor's, not recovery's: the handoff claim, the drain, then
`SwapConductor._swap(record)`, which is `_run_claimed` without `_prepare`, the record already
existing. So the fix is a conductor entry point that takes a record instead of an escalation slot,
started beside the seam after the boot publish the way the tier healer is, with recovery sparing
the record it hands over rather than failing it. Two facts shape it. Its events have no stream to
ride, since the `Converse` stream died with the process, so the answer reaches the user only
through history, where `BrainPhase._persist` already writes it. And the phase restarts from the
snapshot: after `_persist_snapshot` the record is written only by `transition`, which sets its state
and failure reason, so any tool the deep model dispatched before the crash runs again, which is the
double-run the dedup registry exists to prevent.

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
- 2026-09-13: claims held to the code again and all of them stand. `recover_handoffs` still fails
  the stranded record and converges residency without re-running the deep phase, `HandoffRecord`
  still carries the brief, the fence nonce, the taint ledger, the turn-wide budget's position, the
  rounds spent and the loop tail in order, and nothing in the brain's source spells a request id or
  an idempotency key; the word appears only where a control verb describes itself as idempotent.
  The trigger has not fired.
- 2026-09-19: the record, the conductor and boot recovery were read against the entry, and the
  claims about them hold: `HandoffRecord` has gained no field, the conductor fails the record on
  every in-process teardown so only a process death strands one, and
  `grep -rniE 'request_id|idempotency'` over the proto and the brain's source has no hit. Two things
  had moved. The escalation switch became settable from a host `.env` on 2026-09-17, so the
  negative claim that no deployment can strand a handoff was struck. The remedy was wrong about
  where the resume runs: recovery is awaited before the seam serves, so the resume is a conductor
  entry point run beside the seam, and the trigger now names the grep that answers it. The
  trigger has not fired.
