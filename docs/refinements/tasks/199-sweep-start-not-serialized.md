# The sweep's start fenced but not serialized

**Status:** open, fix when it bites
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** A handoff refused at its fit check with a peer a retry pass had just started.

The sweep's start is fenced against a handoff but not serialized with one.
Opened 2026-08-11 by the close above, which owns the fence and says plainly what the
fence does not cover. A pass reads the handoff claim and the residency scope flag synchronously
in the instant before it starts a tier, so a handoff cannot **begin** between the check and the
call. What is not excluded is the other order: a `start` already on the wire when a handoff
begins, whose request the daemon happens to serve after the swap in's own `stop` of that same
tier, leaving a peer loading beside the deep model. Reaching it means one loopback request
outliving the claim, the whole drain, the lease wait, a `boot_id` round trip and a full cortex
stop, so it is narrow, and what it costs is bounded: the fit check reads the card immediately
before the deep load and refuses the handoff with both figures, or the peer runs until
`restart_evicted` finds it already up. Nothing is lost and no record is corrupted, which is why
the residual was taken. The fix is a primitive that orders the two rather than a wider flag, and
the obvious one is refused for a reason that has not changed: taking the GPU lease for the start
would park a user's turn behind a control call and can block a pass for the whole load bound,
which is worse than the failure it prevents. The trigger is a deployment observed refusing a
handoff at its fit check with a peer that a retry pass had just started, which is also the first
evidence that the window is wide enough to reach.

## Trail

- 2026-08-11: Opened by the tier sweep's close, which owns the fence and says plainly what the fence
  does not cover. The residual was taken because nothing is lost and no record is corrupted, and the
  obvious primitive is refused for a reason that has not changed, taking the GPU lease for the start
  parking a user's turn behind a control call.
