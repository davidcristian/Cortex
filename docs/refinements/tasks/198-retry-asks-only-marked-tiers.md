# The retry only asks about tiers believed missing

**Status:** landed 2026-08-11
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

The retry only asks about tiers already recorded as missing. Opened
2026-08-09 by the close above, whose record is written at exactly one site, the swap back's
best-effort restart, and only where the host **refused**. Three shapes escape it: a peer that
accepted its start and then failed to load (measured against the real sidecar, `200 loading`
then `failed` with exit code 1), a peer that dies between handoffs and is never reported, and a peer a
deployment never started at all. A fourth joined them on 2026-08-09 when boot recovery became a
writer of the same record: a boot that could not reach the host marks nothing at all, by design,
since nothing was asked to run, so a sidecar that comes up a minute later has its peers
unretried until the next handoff. In each the placer keeps sending spawns to a dead endpoint and
pays the dead attempt plus the CPU re-run this entry's parent exists to avoid. The fix is a
sweep: the same pass asking `status` for **every** `evict_models` tier rather than only the
marked ones, which costs one control call per tier per interval and closes the whole family. It
is not built now because a sweep that may `start` a tier is a much stronger thing to hold
correct against a handoff in flight than one that only retries a known failure, and because
gating the peers inside the swap back instead is the wrong end (it would spend the load bound
per tier inside the turn the user is waiting on). The trigger is the first deployment observed
running with a peer tier dead and nothing reporting it, which is also the first one whose logs say
how often that happens.
**A fifth shape joined on 2026-08-11**, from the opposite direction and now tellable apart at the
port ([ADR-0030 unrostered-tier addendum](../../adr/ADR-0030-brain-handoff.md)): a peer named in
`CORTEX_SWAP_EVICT_MODELS` that the daemon has no artifact for is marked missing at boot, which
is right, and then retried every interval for ever against a roster that cannot grow, since
`ModelNotHostedError` is exactly the answer no retry can change. It costs two control calls a
pass on loopback and a log line, so it is noise rather than harm, and the question it raises is
the one this entry already owns: what a pass looks at. It belongs here rather than in an entry of
its own because the two answers are one design, whether a tier that can never come back stops
being asked about and whether the placer stays closed on it while it is.
**It landed 2026-08-11, hours after that fifth shape joined it and ahead of its trigger**,
recorded at the [ADR-0030 tier-sweep addendum](../../adr/ADR-0030-brain-handoff.md) where both
halves were opened. A pass now asks `status` for **every** `CORTEX_SWAP_EVICT_MODELS` tier rather
than only the marked ones (`residency_sweep.py`), so the record stopped being a list of refusals
and became a reading of the machine taken every interval. Four things about it, two of them
corrections to this entry's own text.
**All five shapes were re-derived against a real supervisor over HTTP before anything was
designed, and the count is four rather than five.** The first four really did leave the placer
spawning at a dead endpoint, each one witnessed: a spawn on the GPU with the record empty, and a
spawn on the CPU with the tier named on `Health` after the sweep. The fifth does not escape at
all and never did, which this entry had already got right: an unrostered tier is marked at boot
and GPU placement really is closed on it. What was wrong about the fifth is its cost, "two
control calls a pass", where a pass asks `status` first and that call is the one that 404s, so
the `start` is never reached and three passes produced three refusals rather than six. It is
retired rather than fixed: `TierFault.UNHOSTED` is recorded once, the tier is skipped by every
later pass, and the placer stays closed on it, which is what the shape asked for.
**"A peer a deployment never started at all" named the wrong deployment**, and the real one is
reachable with escalation on. Boot recovery does start every evictable peer, so the condition is
a convergence that **returned before its restart loop**: a deep model that is resident and
survives SIGKILL, or a cortex that will not settle, answers `False` several calls earlier and
leaves every peer both unstarted and unrecorded. That makes it the same site as the fourth shape
reached by a different failure, which is why one change closes both and why neither needed boot
recovery touched.
**The risk this entry deferred on is answered rather than assumed away.** A sweep may `start`,
and what stops it racing a handoff is a fence that is both wider and later than the old one: the
handoff **claim** as well as the residency scope, so the pass stands down from before the drain
rather than from the eviction, and both flags are re-read synchronously in the instant before
every `start`, with nothing awaited in between. What that leaves is a start already in flight
when a handoff begins, which the supervisor's own per-model lock orders and which costs a refused
handoff rather than a lost one; it is not closed by construction and is recorded below as its own
entry rather than glossed. The rule it replaces, "only a refusal marks", becomes "only an
observation taken outside a handoff marks", which is the stronger of the two: a pass cannot run
while a handoff owns the GPU, and by the time a scope ends the restart has already asked every
peer to come back.
**The record's shape moved and its home did not.** It carries a reason per tier now and nothing
else: no timestamp, no attempt count, since the pass interval already paces the retry and the
seam names the tier rather than its age. It stays in the process, and the sweep is what makes
that obviously right rather than merely convenient: a record re-derived from `status` every
interval is live-resource state of the same kind as the placer's ledger, so a restart rebuilds it
from the machine and a foreign swapper can at worst cost one interval of CPU placement instead of
a record nothing corrects.

## Trail

- 2026-08-09: Opened by the tier-outage close, whose measurement of a tier that accepts a start and
  then dies is what named it.
- 2026-08-11: A fifth shape joined from the opposite direction, an unrostered peer retried for ever
  against a roster that cannot grow, tellable apart at the port for the first time
  ([ADR-0030 unrostered-tier addendum](../../adr/ADR-0030-brain-handoff.md)).
- 2026-08-11: Landed hours after that fifth shape joined it and ahead of its trigger, recorded at
  the [ADR-0030 tier-sweep addendum](../../adr/ADR-0030-brain-handoff.md). A pass now reads `status`
  for every `CORTEX_SWAP_EVICT_MODELS` tier and writes what it hears (`residency_sweep.py`),
  carrying a `TierFault` per tier so an unhosted one is recorded once and skipped for ever. All five
  shapes were driven against a real supervisor over HTTP before anything was designed and the count
  came out four rather than five. One entry opened in its place, the start already on the wire when
  a handoff begins.
- 2026-08-11: An unhosted tier is left closed at the placer once its fault is recorded, its only
  clearing path being the daemon replacement the boot watch already notices.
- 2026-08-11: The area header named this closed entry and missed the open one that replaced it until
  the entries were re-read the same day, with the total right across both errors, which is the
  cancellation the index's third warning describes.
