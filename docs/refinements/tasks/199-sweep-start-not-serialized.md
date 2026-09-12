# The sweep's start fenced but not serialized

**Status:** open, fix when it bites
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** A handoff refused at its fit check, or recorded as having spilled, with a peer a retry pass had just started.
**Verified:** 2026-09-12

The sweep's start is fenced against a handoff but not serialized with one.
Opened 2026-08-11 by the close above, which owns the fence and says plainly what the
fence does not cover. A pass reads the handoff claim and the residency scope flag synchronously
in the instant before it starts a tier, so a handoff cannot **begin** between the check and the
call. What is not excluded is the other order: a `start` already on the wire when a handoff
begins, whose request the daemon happens to serve after the swap in's own `stop` of that same
tier, leaving a peer loading beside the deep model. Reaching it means one loopback request
outliving the claim, the whole drain, the lease wait, a `boot_id` round trip and a full cortex
stop, so it is narrow. The two arms it can end on are not equally cheap. The fit check reads the
card between the last eviction and the deep load, so it refuses the handoff with both figures only
when the peer had already allocated by that reading; a start the daemon serves after it contributes
nothing to the figure compared, and the peer runs until `restart_evicted` finds it already up.
That second arm is a handoff that succeeds overcommitted, which is the case `cadence.py` was
written for: both tiers report ready, free memory afterwards reads like a fit, and throughput is
roughly halved. No state is lost and no record is corrupted, which is what the origin addendum
claimed and is still true; the deep phase's decode rate is not covered by that claim, and that is
what makes the residual worth more than the refused handoff it is usually described as.
The fix is a primitive that orders the two rather than a wider flag, and
the obvious one is refused for a reason that has not changed: taking the GPU lease for the start
would park a user's turn behind a control call and can block a pass for the whole load bound,
which is worse than the failure it prevents. The trigger is a deployment observed refusing a
handoff at its fit check, or recording that handoff as having spilled, with a peer that a retry
pass had just started. Either is the first evidence that the window is wide enough to reach. The
spill half was added once the two arms were told apart: the refusal this entry was opened on needs
the peer to have allocated before the fit check's reading, and the ordering that produces the
residual does not put it there.

## Trail

- 2026-08-11: Opened by the tier sweep's close, which owns the fence and says plainly what the fence
  does not cover. The residual was taken because nothing is lost and no record is corrupted, and the
  obvious primitive is refused for a reason that has not changed, taking the GPU lease for the start
  parking a user's turn behind a control call.
- 2026-09-10: read against the tree and still not fired. `residency_sweep.py` still calls
  `fence()` synchronously and returns when it answers false, immediately before the one
  `await host.start(model)` in the module, so the start is fenced and nothing orders it against a
  handoff that begins after the check. The trigger asks for an observed refusal in a deployment,
  and the handoff is off unless `CORTEX_ESCALATION` is set, which no compose file here sets.
- 2026-09-12: re-derived against the supervisor and still not fired, and the cost was corrected.
  `ModelSupervisor` holds one `asyncio.Lock` per roster id and takes it in all three verbs, which
  orders a start the daemon has begun serving against the stop that follows it and orders nothing
  about which of two requests the daemon serves first, so the entry's mechanism is exact. What the
  entry had wrong is the price of the arm the lock leaves: `swap_in` reads the card once, between
  its last eviction and the deep start, and `cadence.py` says in its own words that a handoff which
  overcommitted succeeds with both tiers reporting ready and the fit check already passed, so the
  peer arm is a spilled handoff at roughly half the deep model's decode rate rather than nothing.
  The trigger grew the spill half accordingly, that arm having become observable when the spill
  watch and the `Health` spill note landed after this entry was opened.
  `residency_sweep.py`'s module docstring was repaired in the same sitting: it presented the
  per-model lock as covering the in-flight start, which is the half of the origin addendum's
  paragraph that is true, without the half that is not.
  Read against [R-200](200-placer-one-bit-per-card.md) and they are not one defect seen twice.
  This one is an ordering residual between two control calls on one loopback client, whose fix is a
  primitive that serializes them; that one is the width of a single boolean in `VramBudgetPlacer`,
  whose fix is a declared tier id in `PlacementRequest`. Neither fix touches the other's object,
  and the two triggers can fire independently.
