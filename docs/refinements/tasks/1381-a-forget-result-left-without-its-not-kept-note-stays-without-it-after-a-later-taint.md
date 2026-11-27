# A forget result left without its not kept note stays without it after a later taint

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-27

`dispatch` leaves `FORGET_NOT_KEPT_NOTE` off the result of a forget call that matched nothing on
a statement `opened_earlier` reads when the call's `TurnStamp` says memory stores the turn
(`keeps_unmatched`, `forget_opened_earlier.py`). A later result of the same turn can still have
`memory_withheld` withhold it: an untrusted result under the default `skip` policy, or a result
holding a picture under either policy. No reading at the call sees that result, so the model
writes its reply without the note, and only a reply saying the fact was noted is corrected, by
`UNKEPT_CLAIM_NOTE` at the close. Keeping the note on every call such a result could follow
would put it on every untainted call under the default policy, where it is false on each turn
memory then stores. Neither shape has been drawn.

## What to do

1. Draw the shape first: a statement after a forget opened by an earlier turn, with a tool whose
   result is untrusted, counting the replies that say the fact was noted.
2. If any do, decide whether the loop adds the note to that earlier result in `working` once
   the ledger turns tainted or opaque, so the model reads it before it replies. That changes a
   message the model has already read, so the server reuses its prompt cache only up to it.

## History

- 2026-11-27: filed from the change that has `keeps_unmatched` read a picture the turn holds at
  the call (`TurnStamp.opaque`).
