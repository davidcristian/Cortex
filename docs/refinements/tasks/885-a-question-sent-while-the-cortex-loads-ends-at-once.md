# A question sent while the cortex loads ends at once instead of waiting for it

**Status:** open, actionable
**Area:** brain
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)
**Verified:** 2026-10-16

After a restart of the model host the cortex takes one full load to serve. A question sent in that
window ends at once in a red bubble, and the person has to watch the link dot and send it again
by hand. The brain already knows the cause: its serving watch reads `the usual assistant is still
loading` from 1 s after the start. Since 2026-10-16 the bubble says the model is still loading
instead of quoting llama-server's JSON, but the turn still fails.

## Reproduction

On the shared GPU stack with the Linux shell
([startup readings](../../readings/startup-order-and-settings.md)): `docker restart` the model host
container, then send `Name two rivers, one line.` through the overlay. The bubble reads
`inference_failed: model 'cortex' is still loading, so it cannot answer yet; ask again once it is
ready`, the store keeps the question alone, and the cortex is `ready` one load later.

## What to do

1. Before the first model call of a turn, read the serving watch. While its fault is a model that
   is still loading, send a status update naming the wait and poll the watch, up to a bound. Make
   the bound a setting sized from a measured cortex load, with that reading and its SM clock in
   the readings, since a card of another speed loads in another time.
2. When the bound passes, end the turn with the loading message it ends with today.
3. Leave every other fault failing at once: a server that is not answering will not start by
   waiting, unless the model host's restart of an exited cortex is under way.
4. Rerun the reproduction above and record the wait in the readings.

## History

- 2026-10-16: filed by the startup flows, which found the turn failing with the raw 503 body; the
  message was fixed the same night and the wait is this task.
