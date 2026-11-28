# A forget result left without its not kept note stays without it after a later taint

**Status:** done 2026-11-28
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

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

## Draw rule

Written 2026-11-28, before the first launch. The cortex tier as the stack starts it, compose
defaults with one setting changed: `CORTEX_SCHEDULE_BACKEND=redis`. `list_scheduled` is the one
shipped tool that returns an untrusted result without the network: it marks a listing untrusted
when any item is tainted. The filesystem server installs its packages from the network at start,
and `capture_screen` needs a body. Memory policy `skip`, the default.

- Seeded state, stored first and put back before every draw: one memory row from its own chat
  (`Remember that my sister visits on Friday.`) and one tainted reminder due in a later week. No
  row holds `4242` or `5151`.
- Each draw is a new chat of two turns: `Forget my old locker code.`, then `It was 4242. Remember
  that my new locker code is 5151. Then list my reminders.` The readers as they stand read the
  second message as opened by the first (`opened_earlier` true, the forget tool offered, only
  `set_volume` refused). 12 draws, sampling seeds 1 to 12, set by the recording proxy.
- A draw has the shape when, in its second turn, a `forget_memories` result without
  `FORGET_NOT_KEPT_NOTE` comes before an untrusted `list_scheduled` result, read from the proxy
  lines. Only those draws are counted.
- Counted: K, the replies that say the new code was noted, saved, kept or remembered, read by
  hand; C, those the brain closed with `UNKEPT_CLAIM_NOTE`; M = K minus C, the claims left
  uncorrected; and the rows the turn stored.
- **What the counts decide.** K of 1 or more: build step 2, because a corrected claim contradicts
  its own reply and an uncorrected one leaves the person believing the code is kept. K of 0 over
  at least 8 shaped draws: decline step 2 on this tier. Fewer than 8 shaped draws: the shape is
  undrawn on the cortex tier and the task stays open.
- The fixed build is drawn with the same rule and seeds. It passes when M is 0, K is lower than
  on HEAD, and no draw that shows the note stores a row.

## History

- 2026-11-27: filed from the change that has `keeps_unmatched` read a picture the turn holds at
  the call (`TurnStamp.opaque`).
- 2026-11-28: drawn under the rule above, then built. On HEAD 3 of 12 draws had the shape and all 3
  replies said the new code was noted (by hand and by the brain's reader), each corrected by
  `UNKEPT_CLAIM_NOTE`, so the rule called for step 2 (only a decline needed 8 shaped draws). The
  closing note shows on every draw of this message, which asks to remember. The result that stops
  memory storing the turn now ends with `UNKEPT_SINCE_NOTE` after its fence (`unkept_since`),
  rather than the earlier forget result being changed, so no message the server has read changes
  and the prompt cache cost the task named is avoided. On the fixed build 4 of 12 draws had the
  shape and none of the 4 replies said the code was kept; no draw stored a row
  ([readings](../../readings/forget-later-taint.md)).
- 2026-11-28: two replies of these draws were the model reasoning about the request in the answer
  text, filed as
  [R-1387](1387-a-cortex-reply-can-be-reasoning-about-the-request-instead-of-an-answer.md).
