# Resume a crashed handoff from its record

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-09-19
**Trigger:** the dedup design the `Converse` reconnect entry (R-023) needs, a request id on
`UserTurn` or `ClientEvent` plus an idempotency and resume registry keyed by it, after which
resuming is a conductor entry point run beside the gRPC server. Recheck with
`grep -rniE 'request_id|idempotency' proto/body.proto brain/packages/*/src`: no hit means the
design does not exist and this has not fired.

Boot recovery marks any handoff a crash interrupted `FAILED` and converges the GPU back onto the
cortex ([swap_recovery.py](../../../brain/packages/core/src/cortex_core/swap_recovery.py)). It
does not re-run the deep model's phase, although `HandoffRecord`
([handoff.py](../../../brain/packages/core/src/cortex_core/handoff.py)) holds everything needed
to: the brief, the fence nonce, the whole taint ledger, the turn-wide dispatch budget's position,
the rounds already spent and the loop tail in order.

Replaying it would risk running side-effectful work twice, because nothing records request
identity. The tail may contain tool calls whose results were fed back but whose effects are not
idempotent, and the deep phase's own dispatches would run again. So resume is blocked by what the
record deliberately leaves out, not by anything missing from the turn state. Until then the
failure is the cheaper one and the user asks again.

**Where the resume runs, corrected 2026-09-19.** It does not belong in `recover_handoffs`: the
composition root awaits that in `recover_boot_residency` (`swap_builders.py`) before the gRPC server
serves its first turn, so a deep phase run there would hold every turn off for a model load and a
whole phase. The sequence a resume needs is the conductor's: the handoff claim, the drain, then
`SwapConductor._swap(record)`, which is `_run_claimed` without `_prepare`, the record already
existing. So the fix is a conductor entry point that takes a record instead of an escalation slot,
started beside the gRPC server after the boot publish, the way the tier repair is, with recovery leaving
the record it hands over rather than failing it.

Two facts shape it. Its events have no stream to travel on, since the `Converse` stream died with
the process, so the answer reaches the user only through history, where `BrainPhase._persist`
already writes it. And the phase restarts from the snapshot: after `_persist_snapshot` the record
is written only by `transition`, which sets its state and failure reason, so any tool the deep
model dispatched before the crash runs again, which is the double-run the dedup registry exists to
prevent.

## History

- 2026-07-17: Opened with the brain-handoff conductor sub-slice
  ([ADR-0030](../../adr/ADR-0030-brain-handoff.md) decision 4), which names it as its recorded
  refinement; the area went 3 to 4.
- 2026-07-19: Given a line in the index's pickup order, saying it waits on the same
  request-identity and dedup design the `converse` reconnect entry needs.
- 2026-09-09: Claims checked against the code, and the account of the handoff rebuilt from the
  supervisor and the record. Nothing had been restructured, and the dedup design exists nowhere in
  the brain's source. The trigger has not fired.
- 2026-09-13: Claims checked again and all held. The word idempotency appears only where a control
  verb describes itself as idempotent. The trigger has not fired.
- 2026-09-19: The record, the conductor and boot recovery were read against the entry and its
  claims about them hold: `HandoffRecord` has gained no field, the conductor fails the record on
  every in-process teardown so only a process death strands one, and
  `grep -rniE 'request_id|idempotency'` over the proto and the brain's source has no hit. Two
  things had moved. The escalation switch became settable from a host `.env` on 2026-09-17, so the
  earlier claim that no deployment can strand a handoff was removed. And the remedy was wrong
  about where the resume runs, corrected above. The trigger has not fired.
