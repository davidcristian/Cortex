# A request to remember in another language runs a forget call

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

On 2026-11-12 the `cortexn20` stack stored eight facts, one per new chat, through a brain built
from that night's tree ([readings](../../readings/recalled-memory-reply-language.md)). On 7 of the
8 first requests the cortex called `forget_memories` with the fact's own text, such as
`{"text":"Bello"}` for `Merk dir, dass mein Hund Bello heißt.` `unasked_forget`
(`unasked_tools.py`) refused it on the three English requests that made one and on the Spanish
one. On the French, German and Romanian requests the call ran, matched nothing, and the reply
ended with the note saying nothing was deleted, which the stored exchange row then holds.

The fact reader of `unasked_forget` (`_STATES_A_FACT`) reads English only, a choice the
[language flows](../../readings/overlay-language-and-locale-flows.md#8-requests-to-remember-in-four-more-languages)
record: a request to remember in another language keeps the forget tool unless it states the fact
in an English form, since a tool refusal keeps the tool when unsure. On 2026-11-07 the same French,
German and Romanian requests made no forget call in 9 draws. When a stored row holds the call's
text, the call lists that row on a destructive card for a message that asked to keep it.

Reproduction: send `Merk dir, dass mein Hund Bello heißt.` in a new chat and read the proxy log
for a `forget_memories` call on the first request.

## What to do

1. Before any draw, write rows and a rule into a readings record: the four requests to remember
   of the language flows, each beside a stored row holding the call's likely text, drawn three
   times on the stack brain, counting forget calls that ran and cards shown.
2. If calls run, read the fact in the four languages in `_STATES_A_FACT` (a possessive such as
   `mon`, `mein`, `mi`, `meu` before a noun and a verb of being), with statements that ask to
   forget in each language written as tests first, and every recorded draw message replayed
   through the old and new reader.

## History

- 2026-11-12: filed from the setup of the recalled memory language draws, where three of four
  requests to remember in another language ran a forget call.
