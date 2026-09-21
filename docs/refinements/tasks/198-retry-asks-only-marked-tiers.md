# The retry only asks about tiers believed missing

**Status:** done 2026-08-11
**Area:** resource-governance
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)

The tier fault record was written at exactly one site, the swap back's best-effort restart, and only
where the host refused. Four cases escaped it: a peer that accepted its start and then failed to
load (measured against the real sidecar, `200 loading` then `failed` with exit code 1), a peer that
dies between handoffs, a peer a deployment never started, and a boot that could not reach the host,
which marks nothing by design. In each the placer keeps sending spawns to a dead endpoint and pays
the dead attempt plus the CPU re-run.

Fixed on 2026-08-11, recorded at [ADR-0054](../../adr/ADR-0054-baseline-residency.md) decision 4. A
pass now asks `status` for every `CORTEX_SWAP_EVICT_MODELS` tier rather than only the marked ones
(`residency_pass.py`), so the record stopped being a list of refusals and became a reading of the
machine taken every interval.

All the cases were driven against a real supervisor over HTTP before anything was designed, and the
count came out four rather than five. The fifth, a peer named in `CORTEX_SWAP_EVICT_MODELS` that the
daemon has no artifact for, does not escape at all: it is marked missing at boot and GPU placement
really is closed on it. What was wrong about it is its cost, "two control calls a pass", where a
pass asks `status` first and that is the call that 404s, so the `start` is never reached. It is
retired rather than fixed: `TierFault.UNHOSTED` is recorded once, the tier is skipped by every later
pass, and the placer stays closed on it.

"A peer a deployment never started at all" named the wrong deployment. Boot recovery does start
every evictable peer, so the real condition is a convergence that returned before its restart loop:
a deep model that is resident and survives SIGKILL, or a cortex that will not settle, answers
`False` several calls earlier and leaves every peer both unstarted and unrecorded. That makes it the
same site as the boot case reached by a different failure, which is why one change closes both.

The risk this entry deferred on is answered rather than assumed away. A pass may `start`, and what
stops it racing a handoff is a check that is both wider and later than the old one: the handoff
claim as well as the residency scope, so the pass stands down from before the drain rather than from
the eviction, and both flags are read again synchronously in the instant before every `start`, with
nothing awaited in between. What that leaves is a start already in flight when a handoff begins,
which the supervisor's own per-model lock orders and which costs a refused handoff rather than a
lost one; it is recorded below as its own entry. The rule it replaces, "only a refusal marks",
becomes "only an observation taken outside a handoff marks".

The record has a reason per tier and nothing else, no timestamp and no attempt count, since the pass
interval already paces the retry. It stays in the process, which the pass makes obviously right: a
record recomputed from `status` every interval is live-resource state of the same kind as the
placer's ledger, so a restart rebuilds it from the machine.

## History

- 2026-08-09: Opened by the tier-outage close, whose measurement of a tier that accepts a start and
  then dies is what named it.
- 2026-08-11: A fifth case joined from the opposite direction, an unrostered peer retried for ever
  against a roster that cannot grow, distinguishable at the port for the first time
  ([ADR-0053](../../adr/ADR-0053-model-host-supervisor.md) decision 14).
- 2026-08-11: Closed hours later and ahead of its trigger. One entry opened in its place, the start
  already sent when a handoff begins.
- 2026-08-11: An unhosted tier is left closed at the placer once its fault is recorded, its only
  clearing path being the daemon replacement the boot watch already notices.
