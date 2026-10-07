# A turn sent while another runs in the same chat interleaves the chat

**Status:** open, actionable
**Area:** session-history
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md) decision 1
**Verified:** 2026-10-07

The brain serialises turns within one `Converse` stream (`_enqueue_turn` in
`converse_stream.py`), but nothing orders two streams that name the same session. Each turn stores
its question when it starts and its reply when it ends, so a second turn that starts before the
first one ends stores its question between the first question and the first reply. On 2026-10-07
a question sent after a Stop, while the stopped turn still generated, left the chat's list as
question, question, reply, reply, and the follow-up's prompt held the first question with no reply
([readings](../../readings/overlay-turn-flows.md#stop)). A reopened chat shows the two questions
together and the two replies after them, and every later prompt is built from that order.

Stop is one way in; two clients, or a resend after a lost stream, are others. A per-session turn
lock in the core, taken around the whole turn including its writes, makes the second turn wait
and then read the first one's reply, which is the order the person saw. One brain process serves
every stream today, so the lock can be a map of `asyncio.Lock`s; a Redis key behind the
`SessionStore` port would be needed only if several brain processes served one session. [R-127](127-multi-turn-and-proto-cancel.md)
removes the wait after a Stop by ending the stopped turn; it does not cover the other ways in.

## History

- 2026-10-07: filed from the Stop flow on the Linux shell, with R-127's trigger fired by the same
  run.
