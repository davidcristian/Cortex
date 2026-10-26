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

Approving the card would remove every tainted memory the chat reads, which the person did not ask
for, and leave the new value to be recorded only as the exchange.

## Reproduction

On the shared stack, send a dozen or more "Please remember this: ..." statements, each in a new
chat, for example "I live in Lyon." and then "I live in Porto.". Read the `cortex.tools.audit` lines
for `forget_untrusted_memories`, or the card on the shell.

## What to do

1. Write rows and a pass rule in the readings first: a set of remember, update and correct
   requests, each in a new chat, with no request to forget; pass when no row calls the tool. Run
   them on the current build to measure the rate.
2. If the rate is above zero, try a change measured on the same rows: a description that says the
   tool never updates or replaces a fact, or a check in the dispatcher that offers the tool only on
   a turn whose text asks to forget, as a typed refusal the model reads.

## History

- 2026-10-26: filed from the memory over time flows on the Linux shell.
