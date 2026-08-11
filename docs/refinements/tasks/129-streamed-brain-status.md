# Streamed brain status

**Status:** open, a seam or port change comes first
**Area:** body-overlay
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Trigger:** A consumer that needs the brain to speak first, meaning a status the overlay cannot ask for at the moment it changes rather than on its next 5 s recheck.

The push half this
entry originally assumed, still unbuilt, and now with a named blocker rather than a wish:
**nothing produces a status the overlay cannot ask for.** The brain's `Health` answers
`ready = True` unconditionally (`server.py`), and a mid-turn `StatusUpdate` already reaches
the overlay on the `Converse` stream as a chip. So the amber "not ready" path ships shaped and
tested with no producer, and the rule that any successful call means ready is honest only
while that holds. Both change together when the model manager (Slice 11) can make the brain
not-ready *between* turns: that is when a push earns its keep and when "any success means
ready" stops being true.
**Half the producer landed 2026-07-17 with the brain-handoff conductor
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) decisions 6 and 7).** An escalating turn now
streams `StatusUpdate(state="swapping")` through drain, load, work, and restore on the
`Converse` stream the user already holds, so the swap window says what it is doing, with no
proto change (the overlay renders it as a chip today).
**The producer is whole as of 2026-07-18** (the honesty-surfaces sub-slice, ADR-0030 decision
6): `Health` reads the swapping manager's published residency and answers `ready=false` with a
truthful detail while the deep model is loading, working, or being swapped back, after a
restore that gave up, and (from the 2026-07-18 audit repair) after a boot whose recovery could
not settle the cortex, which was the one machine state the first landing still called ready.
The blocker this entry named is therefore met and the entry is **no
longer blocked**, with **zero overlay change**, exactly as designed: the landed indicator
already classifies a not-ready reply as amber `Degraded` and shows the brain's line verbatim,
and the 5 s recheck (visible-and-unhealthy) turns it green again on its own when the cortex is
back. Two limits worth knowing before the push half is designed against them. The amber shows
**between** turns only: the reducer folds every streamed event as proof of serving, so during
the escalating turn's own stream the dot is green and the chips carry the story instead. And a
handoff's **drain** is deliberately still ready, the cortex being resident and answering
throughout it. What remains deferred is only the **push** itself: a server-streamed status RPC
is a seam change (proto + both stubs + a consumer), and probe-on-summon plus the escalating
stream's own chips cover personal scale, so it waits for a consumer that needs the brain to
speak first.

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
