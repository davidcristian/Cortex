# The brain forgetting that escalation cannot work

**Status:** done 2026-08-16
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Boot recovery told the operator once, at startup, that the deep tier is not in the model host's
roster, and kept no record of it. Every later escalation therefore ran the whole preparation against
a tier that cannot exist: the pool was drained, the cortex evicted, the `start` came back 404, and
the scope's `finally` reloaded the cortex, which at tier scale is minutes of the assistant being
gone for a handoff that was never going to run, once per attempt.

Fixed on 2026-08-16 ([ADR-0030 decision 11](../../adr/ADR-0030-brain-handoff.md)), and the first of
the two decisions went the other way from the entry: the fact is stored nowhere.
`SwapConductor._prepare` asks the host through a new `ResidencyController.unhosted(model)` verb,
before the store is touched and long before the drain, and refuses with a note saying the machine has
no deep model set up. Keying a cached result to the boot id would have cost one control call at the
moment of use anyway, since the reconcile that detects a replaced daemon runs inside the residency
scope and cannot be moved above the drain, so at equal cost the version with no state and no
staleness window was chosen. The second decision stands as the entry framed it: the brain reports
nothing new over the wire, and the surfaces that report it are the turn's own stream and the log.

Measured against the real sidecar with `brain` absent from its roster: the preparation this removes
took 29.7 s of the assistant being off the card on a gemma-4-12B cortex, and the refusal takes under
0.01 s.

## History

- 2026-08-11: Opened by the unrostered-tier close.
- 2026-08-16: Closed as a refusal computed at the moment of use rather than a remembered one, with
  the note arriving before the stall instead of after it, and the record-settling half of the
  conductor split into `swap_settle.py` to stay under the line limit. It opened one narrower entry,
  [R-279](279-confirm-card-offers-an-impossible-handoff.md): the user still approves a card for a
  handoff that is then refused, because every surface earlier than the conductor is on the per-turn
  hot path.
