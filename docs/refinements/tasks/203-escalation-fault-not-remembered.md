# The brain forgetting that escalation cannot work

**Status:** landed 2026-08-16
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Boot recovery detects at startup that escalation cannot work and records that nowhere. Opened
2026-08-11 by the close above, which tells the operator once, at startup, that the deep tier is not
in the model host's roster and then keeps no record of it. Every later escalation therefore runs the
whole prologue against a tier that cannot exist: the pool is drained, the cortex is evicted, the
`start` comes back 404, and the scope's `finally` reloads the cortex, which at tier scale is minutes
of the assistant being gone for a handoff that was never going to run, once per attempt. The user's
note says the tier is not in the roster, which is accurate but arrives after the stall. The fix is
to record that fact where the conductor reads it and fail before the drain, and it is recorded
rather than built because it needs two decisions this close did not need: where a fact about the
host's roster lives on a brain whose every other cached fact about that daemon is invalidated by a
restart (the boot id is the existing answer to exactly that question, so the refusal has to be
re-derived when the daemon changes, not cached for the life of the process), and what the seam says
about a capability that is configured and unavailable, the residency report carrying one detail line
that already belongs to the peer record.

**Landed 2026-08-16, and the first of those two decisions went the other way** ([ADR-0030
unrostered-refusal addendum](../../adr/ADR-0030-brain-handoff.md)). The fact lives nowhere:
`SwapConductor._prepare` asks the host through a new `ResidencyController.unhosted(model)` verb,
before the store is touched and long before the drain, and refuses with a note saying the machine
has no deep model set up. Keying a cached verdict to the boot id would have cost one control call at
the moment of use anyway, since the reconcile that detects a replaced daemon runs inside the
residency scope and cannot be hoisted above the drain, so at equal cost the version with no state
and no staleness window was chosen. The second decision stands as the entry framed it: the seam says
nothing new, the readiness dot's one detail line stays the peer record's, and the surfaces that
report it are the turn's own stream and the log. Measured against the real sidecar with `brain`
absent from its roster: the prologue this removes took 29.7 s of the assistant being off the card on
a gemma-4-12B cortex, and the refusal takes under 0.01 s.

## Trail

- 2026-08-11: Opened by the unrostered-tier close, which tells the operator once at startup that the
  deep tier is not in the model host's roster and keeps that knowledge nowhere, so every escalation
  still drains the pool, evicts the cortex and reloads it to rediscover the same 404, once per
  attempt and at tier scale minutes of the assistant being gone.
- 2026-08-16: Landed as a re-derived refusal rather than a remembered one, with the note arriving
  before the stall instead of after it, and the record-settling half of the conductor split into
  `swap_settle.py` to make room under the line cap. It opened one narrower entry,
  [R-279](279-confirm-card-offers-an-impossible-handoff.md): the user still approves a card for a
  handoff that is then refused, because every surface earlier than the conductor is the per-turn
  hot path.
