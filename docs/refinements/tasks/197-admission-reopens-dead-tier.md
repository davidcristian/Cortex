# Admission reopening onto a tier that would not restart

**Status:** landed 2026-08-09
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Admission reopens even onto a tier the swap back could not restart.
Opened 2026-07-18 by the pass that made the drain window wait for the standing residency, and
recorded at the [ADR-0030 reopening addendum](../../adr/ADR-0030-brain-handoff.md), that ADR owning
both halves that create it (the best-effort tier restart and the reopening that follows the
restore) while this port stays unchanged. The
window now lifts only after the residency scope has restored the cortex and restarted every
`evict_models` tier, and every reopening is witnessed against what was actually running. But
the tier restart is deliberately best effort ([ADR-0030](../../adr/ADR-0030-brain-handoff.md)
decision 4: a tier that will not come back must not be reported as the cortex being gone), so a
`ModelHostError` on that start is logged and swallowed, and `undrain` then reopens admission
onto a subagent server that is not running. The next delegated run fails at its backend and
degrades to an `ok=False` result, which is honest but wasteful, and nothing retries the tier
until the next handoff or a restart. **Reachable by configuration since 2026-07-18**, which
replaces this entry's original "nothing is at stake today, `CORTEX_SWAP_EVICT_MODELS` is empty
until the real lifecycle sub-slice, so no tier is ever evicted": that sub-slice has landed, so a
deployment that names a GPU subagent artifact and lists that tier in `CORTEX_SWAP_EVICT_MODELS`
now really does evict it and can really see it refuse to come back. It stays unreachable in the
**shipped defaults** (both of those are empty), and its cost fell in the same sub-slice: a spawn
placed on a tier that did not restart now re-runs once on the CPU rather than only reporting, so
what is left is a wasted GPU attempt per spawn instead of a lost one. Still recorded rather than
built, for the same reason. The fix wants a residency
state that knows a tier is down, so the placer skips it while something retries the start,
rather than a scheduler change, which is why it is recorded
here and not built: keeping the pool drained instead would be worse, since it would trade every
delegated run for the ones that would have been placed on that one tier.
**The honesty-surfaces sub-slice landed on 2026-07-18 and did NOT clear this**, which this entry
used to imply it would. What that sub-slice introduced is one published `ResidencyReport` about
what the GPU is serving, for the seam's `Health` to answer with (`residency_state.py`), and it is
deliberately narrow: it carries no per-tier state at all, so there is still nothing for a placer
to read. Widening it is the same shape of change it always was, now with a place to put it.
**It landed 2026-08-09**, ahead of its trigger, recorded at the
[ADR-0030 tier-outage addendum](../../adr/ADR-0030-brain-handoff.md) where the entry was opened and
at the [ADR-0012 addendum](../../adr/ADR-0012-resource-governance.md) that owns the port. A peer
the swap back could not restart is now recorded in `StandingTiers` (`residency_tiers.py`), which
closes GPU placement, names the tier on a **serving** `Health` reply, and is retried every
`CORTEX_SWAP_TIER_HEAL_S` (30 s) by `TierHealer` until a pass sees the tier `ready`. Four things
about it, two of them corrections to this entry's own text.
**"This port stays unchanged" was the half that moved**, and it is the phrasing this file's own
index warns about. The scheduler really is untouched. The **placer** port is not: `place` is
synchronous, lock-free and argument-poor by design, so nothing can *ask* it whether a tier is
up, and the only shape that fits is being *told*, which is a verb. `SubagentPlacer` gained
`close_gpu()`/`open_gpu()`, deliberately not expressed as a charge, since a resident charged
large enough to crowd the cap out would say "no room" where the truth is "no server" **and**
would be silently reversed by the next successful `charge_standing`.
**"Widening `ResidencyReport`" was the other correction**, and the reason is a lifetime rather
than a shape: that value is republished at every residency transition, so down-ness written into
it would be dropped by the next swap in, which publishes `RESIDENCY_LOADING` and knows nothing
about peers. The record lives beside the report and is folded in on read, which is also what
keeps the swap to one writer of what the GPU is serving.
**The distinction the entry never named is the one the design turns on**: down versus merely
evicted. Only a `start` that **raised** marks, only a **serving** report is annotated, and the
handoff window is covered by the drain and the charge rather than by this, so a tier stopped for
the length of a swap never reads as a fault. **What the user sees needed no new surface**:
`HealthReply` already carries a detail beside `ready` and the overlay already renders a ready
detail as `Brain ready: <line>`, so a serving report with something to say simply wins the slot
the version string held, with no proto, Rust or TypeScript change.
**Its cost claim held and its harm claim shrank.** "A wasted GPU attempt per spawn" is exactly
what this removes. What it does not remove is a tier that dies **without** anybody having asked
it to restart, which was measured against a real sidecar the same day: a tier with a bad
artifact answers `200 loading` to a `start` and `failed` seconds later, so the restart loop marks
it standing and nothing notices. That is the first of the three entries below.

## Trail

- 2026-07-18: Opened by the pass that made the drain window wait for the standing residency rather
  than for the enclosing `finally` to get there first, recorded at the
  [ADR-0030 reopening addendum](../../adr/ADR-0030-brain-handoff.md). The defect behind that pass was
  fixed rather than deferred, the shielded restore having waited for one cancellation where the seam
  delivers two.
- 2026-07-18: The model-host sub-slice made it reachable by configuration for the first time and cut
  its cost, a spawn placed on a dead tier now re-running once on the CPU rather than only reporting.
- 2026-07-18: The honesty-surfaces sub-slice landed and did not clear it, the published
  `ResidencyReport` carrying no per-tier state for a placer to read.
- 2026-08-09: Landed ahead of its trigger, recorded at the
  [ADR-0030 tier-outage addendum](../../adr/ADR-0030-brain-handoff.md) and at the
  [ADR-0012 addendum](../../adr/ADR-0012-resource-governance.md) that owns the port. Its account of the
  code was re-derived first and held on three points and moved on two, the port and its own proposal
  to widen `ResidencyReport`. The failure side was witnessed against a real `model-host` container
  over real HTTP, both a tier the daemon refuses outright and one that accepts a start and dies, and
  three entries opened in its place.
- 2026-08-09: The three points that held are named in the record of that re-derivation: the restart
  really is best effort, `undrain` really does reopen on every path, and `ResidencyReport` really
  carries no per-tier state.
