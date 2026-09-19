# Streamed brain status

**Status:** open, a seam or port change comes first
**Area:** body-overlay
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-09-19
**Trigger:** A consumer that needs the brain to speak first, meaning a status change the overlay must show while it is on screen and green, where today it would be read only on the next summon, because the 5 s recheck runs only while the link is already not ready.

What is deferred here is the **push**: a server-streamed status RPC, so the brain can say what it
is doing at the moment it changes rather than when the overlay next asks. The blocker the entry
opened with is long gone, and what is left is a consumer.

The entry was filed on 2026-07-16 behind the landed connection indicator, when nothing on the
brain's side produced a status the overlay could not ask for: `Health` answered ready
unconditionally, so the amber path shipped shaped and tested with no producer. The producer arrived
in two pieces. An escalating turn streams `StatusUpdate(state="swapping")` through drain, load,
work and restore on the `Converse` stream the user already holds, with no proto change
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) decisions 6 and 7). Then `Health` began reading
the swapping manager's published residency and answering `ready=false` with a truthful detail while
the deep model is loading, working or being swapped back, after a restore that stopped retrying,
and after a boot whose recovery could not settle the cortex.

None of that needed an overlay change, which is what the indicator was designed for: it classifies
a not-ready reply as amber `Degraded`, shows the brain's line verbatim, and its 5 s recheck turns
the dot green again on its own once the cortex is back. Two limits are worth knowing before the
push is designed against them. The amber shows **between** turns only, the reducer folding every
streamed event as proof of serving, so during an escalating turn's own stream the dot is green and
the chips carry the story instead. And a handoff's drain is deliberately still ready, the cortex
being resident and answering throughout it.

So the push waits on a consumer rather than on a producer. It is a seam change, proto plus both
stubs plus something that reads it, and probe-on-summon together with the escalating stream's own
chips covers this scale.

## Trail

- 2026-07-16: Opened behind the landed connection indicator, blocked on a producer, since nothing
  produced a status the overlay could not ask for.
- 2026-07-17: Half the producer landed with the brain-handoff conductor, an escalating turn
  streaming `StatusUpdate(state="swapping")` through drain, load, work and restore on the stream the
  user already holds, with no proto change.
- 2026-07-18: The producer became whole with the honesty-surfaces sub-slice, `Health` reading the
  swapping manager's published residency and answering `ready=false` with a truthful detail, which
  lit the landed indicator amber with zero overlay change. This was the last entry in the backlog
  blocked on a producer, and it moved from blocked on the model-swap slice to waiting on a seam
  change plus a consumer.
- 2026-09-13: Re-derived, and the trigger has not fired. `BrainService` declares one server-streamed
  RPC, `Converse`, and the other eleven are unary, so nothing pushes a status; the overlay's
  `LINK_RECHECK_MS` is still 5000 and still the only thing that asks. The producer half reads as
  described: `Health` returns the residency's not-serving detail, its serving detail, or the
  server's version string, in that order. The body of this entry was rewritten to say that once,
  because it still opened with the 2026-07-16 reading that `Health` answers ready unconditionally
  and then refuted it twice further down, so the first thing a reader met was the claim the entry
  exists to withdraw.
- 2026-09-19: Re-derived, and the trigger has not fired: the proto still declares one
  server-streamed RPC and `LINK_RECHECK_MS` is still 5000 in `body/app/src/overlay/useLink.ts`.
  Two corrections. `BrainService` declares eleven RPCs, not twelve, so the unary ones number ten
  rather than the eleven written above, a count unchanged since the preferences pair landed on
  2026-07-19. And the trigger described the push as beating "the next 5 s recheck", which exists
  only while the link is already not ready: `useLink` arms that interval when the view is visible
  and unhealthy, and a green link on screen is probed again only on the next summon. The gap a push
  would close is therefore a change away from green while the overlay is open, and the trigger now
  says so. ADR-0011's own account of the recheck was already right.
