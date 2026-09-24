# Streamed brain status

**Status:** open, needs a port change first
**Area:** body-overlay
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-09-24
**Trigger:** A status change that begins while no turn from this overlay is streaming and must change the dot's colour: a second client that can start a handoff, or a background job that escalates. A change that one of this overlay's own turns leaves behind is read by the probe that follows the turn, not by a push.

What is deferred is the push: a server-streamed status RPC, so the brain can say what it is doing
at the moment it changes rather than when the overlay next asks. The producer this entry was
blocked on exists; what is left is a consumer.

The producer arrived in two pieces. An escalating turn streams `StatusUpdate(state="swapping")`
through drain, load, work and restore on the `Converse` stream the user already holds, with no
proto change ([ADR-0030](../../adr/ADR-0030-brain-handoff.md) decisions 6 and 7). Then `Health`
began reading the swapping manager's published residency and answering `ready=false` with a true
detail while the deep model is loading, working or being swapped back, after a restore that
stopped retrying, and after a boot whose recovery could not settle the cortex.

None of that needed an overlay change: the indicator classifies a not-ready reply as amber
`Degraded`, shows the brain's line as given, and its 5 s recheck turns the dot green again once
the cortex is back. Two limits are worth knowing before the push is designed against them. The
amber shows between turns only, because the reducer treats every streamed event as proof the brain
is serving, so during an escalating turn's own stream the dot is green and the chips tell the
story. And a handoff's drain is deliberately still ready, the cortex being resident and answering
throughout it.

The push is a proto change plus both stubs plus something that reads it. Probing on summon,
together with the escalating stream's chips, covers this scale.

The push is a different axis from the shape of one reply, which
[R-320](320-one-detail-string-two-facts.md) settled as a `notes` list on `HealthReply`: this entry
is when a reply is sent. A stream would send the same message `Health` answers, so it needs nothing
from that change and that change needed nothing from it.

## History

- 2026-07-16: Opened behind the connection indicator, blocked on a producer, since nothing
  produced a status the overlay could not ask for and `Health` answered ready unconditionally.
- 2026-07-17: Half the producer shipped with the brain-handoff conductor.
- 2026-07-18: The producer became whole with the honesty-surfaces sub-slice, which lit the
  indicator amber with no overlay change. This was the last entry in the backlog blocked on a
  producer, and it moved to waiting on a port change plus a consumer.
- 2026-09-13: Checked again; the trigger has not fired. `BrainService` declares one
  server-streamed RPC, `Converse`, and the rest are unary, so nothing pushes a status; the
  overlay's `LINK_RECHECK_MS` is still 5000 and still the only thing that asks. `Health` returns
  the residency's not-serving detail, its serving detail, or the server's version string, in that
  order. The body of this entry was rewritten, because it still opened with the 2026-07-16 reading
  that `Health` answers ready unconditionally and then withdrew it twice further down.
- 2026-09-19: Checked again; the trigger has not fired. Two corrections. `BrainService` declares
  eleven RPCs, not twelve, so the unary ones number ten rather than eleven, a count unchanged
  since the preferences pair shipped on 2026-07-19. And the trigger described the push as beating
  "the next 5 s recheck", which exists only while the link is already not ready: `useLink`
  starts that interval when the view is visible and unhealthy, and a green link on screen is
  probed again only on the next summon. The gap a push would close is a change away from green
  while the overlay is open, and the trigger now says so.
- 2026-09-24: Checked again; the trigger has not fired, and it was restated so it can be decided.
  Every status change today starts inside one of the overlay's own turns: a handoff is started only
  by the engine `for_stream` builds in `engines.py`, and a scheduled task runs a subagent through
  `spawn_subagents` and never escalates. A peer tier's fault is the one change from outside a turn,
  and it changes only the tooltip under a green dot. The one gap found was at the end of a turn: a
  swap back that gave up publishes `RESIDENCY_LOST` before the turn's last events, and every event
  sets the dot green, so it stayed green until the next summon. The overlay knows when its own turn
  ends, so that gap needed a pull rather than a push: `useLink` now probes once when a turn ends on
  screen with the link green.
