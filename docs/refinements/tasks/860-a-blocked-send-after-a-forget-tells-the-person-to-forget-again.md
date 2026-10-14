# A blocked send after a forget tells the person to forget again

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-10-14

When the person approves `forget_untrusted_memories` on a recall-tainted turn, the cortex can go on
to call the blocked tool in the same turn without being asked. The turn already recalled a tainted
memory, so the call returns `RECALL_DENIED_MSG`, which tells the model to say the person can ask to
forget those memories. The reply then reads "I was unable to send the email ... You can ask me to
forget the memories derived from untrusted content, and then you can ask me to send the email
again", right after the forget ran, and does not say the forget succeeded. The store held no rows
afterwards and a new message's send reached its card, so only the reply is wrong.

## Reproduce

Empty memory and run the two seed chats of [recall-tainted-send.md](../../readings/recall-tainted-send.md).
On the overlay, ask for the bulb order send (blocked, the reply names forgetting), then in the same
chat "Please forget the memories derived from untrusted content." and press Approve. The audit
shows `forget_untrusted_memories` ok, then `send_email` with `RECALL_DENIED_MSG`. Seen in 1 of 1
approved forget on 2026-10-14: [overlay repeat and forget
flows](../../readings/overlay-repeat-and-forget-flows.md#forgetting-from-the-overlay).

## What to do

A result text, not a prompt rule: when a turn's `forget_untrusted_memories` call has succeeded, a
later recall-denied call in that turn returns a text saying the memories are already forgotten and
that a new message asking for the action will run it. Write the rows and the pass rule into
[forget-untrusted-memories.md](../../readings/forget-untrusted-memories.md) before drawing them:
the forget request on a tainted turn, approved, counted when the turn calls the blocked tool after
the forget.

## History

- 2026-10-14: filed from the overlay flows of that night.
