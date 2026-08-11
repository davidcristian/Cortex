# The brain forgetting that escalation cannot work

**Status:** open, fix when it bites
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** A deployment observed paying that stall, or a user asking why escalation never happens.

The brain learns at boot that escalation cannot work, and then forgets it.
Opened 2026-08-11 by the close above, which tells the operator once, at startup, that
the deep tier is not in the model host's roster, and keeps that knowledge nowhere. Every later
escalation therefore runs the whole prologue against a tier that cannot exist: the pool is
drained, the cortex is evicted, the `start` comes back 404, and the scope's `finally` reloads the
cortex, which at tier scale is minutes of the assistant being gone for a handoff that was never
going to run, once per attempt. The user's note says the tier is not in the roster, which is
honest but arrives after the stall. The fix is to remember the fact where the conductor can read
it and refuse before the drain, and it is recorded rather than built because it needs two
decisions this close did not need: where a fact about the host's roster lives on a brain whose
every other belief about that daemon is invalidated by a restart (the boot id is the existing
answer to exactly that question, so the refusal has to be re-derived when the daemon changes,
not cached for the life of the process), and what the seam says about a capability that is
configured and unavailable, the residency report carrying one detail line that already belongs to
the peer record. The trigger is a deployment observed paying that stall, or a user asking why an
escalation that was offered never happens.

## Trail

- 2026-08-11: Opened by the unrostered-tier close, which tells the operator once at startup that the
  deep tier is not in the model host's roster and keeps that knowledge nowhere, so every escalation
  still drains the pool, evicts the cortex and reloads it to rediscover the same 404, once per
  attempt and at tier scale minutes of the assistant being gone.
