# A request to remember a fact can raise the forget card

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md) decision 9
**Verified:** 2026-10-26

After "Please remember this: I live in Lyon." was stored, "Please remember this: I live in Porto."
in a new chat made the cortex call `forget_untrusted_memories`, so the overlay showed its confirm
card ([readings](../../readings/overlay-memory-over-time-flows.md#a-fact-contradicted-with-no-such-words)).
That tool removes memories derived from untrusted content and updates nothing, and its description
(`memory_forget.py`) already says to call it only when the user asks to forget such memories. The
turn's recall had handed it no memory. Sent again in another new chat, the same statement got
"OK. I've noted that you live in Porto." with no card. Later "Please remember this: my sister's
name is Ana.", with no earlier fact about a sister, raised the card too: 2 of the 22 requests to
remember in those flows.

On the brain directly, 40 requests to remember, update or correct a fact, each in a new chat,
called it on 1 of 40, and on 2 of 40 once its description also said it never saves, updates or
corrects a fact ([readings](../../readings/forget-card-on-remember.md)). Every call came with no
tainted memory in the pool, so approving the card would have removed nothing; with tainted
memories present it would remove every one the chat reads, which the person did not ask for.

## What to do

A description sentence failed, and a dispatcher check on the words of the request is a keyword
match on English. The remedy left is a check on the store: offer the tool only on a turn whose
session can recall at least one tainted memory.

1. Add a count of the tainted memories in a set of scopes to `MemoryStore`, with its contract
   test, the fake and the pgvector adapter.
2. Leave `forget_untrusted_memories` out of the turn's tool list (`tool_loop.py`) when that count
   is zero. A call to it by name on such a turn must still be refused or still raise the card:
   `dispatch_round.py` passes `confirm_required` false for a tool missing from the turn's list,
   and `confirm_names` holds only the configured sidecar tools.
3. Measure on the readings' 40 rows and control under their rule, then the same 40 rows with one
   tainted memory in the pool, where the tool is offered, to record the rate that remains.

## History

- 2026-10-26: filed from the memory over time flows on the Linux shell.
