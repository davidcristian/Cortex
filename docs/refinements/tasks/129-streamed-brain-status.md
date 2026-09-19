# Streamed brain status

**Status:** open, needs a port change first
**Area:** body-overlay
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-09-19
**Trigger:** A consumer that needs the brain to speak first, meaning a status change the overlay must show while it is on screen and green, where today it would be read only on the next summon, because the 5 s recheck runs only while the link is already not ready.

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
