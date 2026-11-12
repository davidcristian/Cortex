# A request to remember in another language runs a forget call

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

On 2026-11-12 the `cortexn20` stack stored eight facts, one per new chat, through a brain built
from that night's tree ([readings](../../readings/recalled-memory-reply-language.md)). On 7 of the
8 first requests the cortex called `forget_memories` with the fact's own text, such as
`{"text":"Bello"}` for `Merk dir, dass mein Hund Bello heißt.` `unasked_forget`
(`unasked_tools.py`) refused it on the three English requests that made one, and
`forget_unrequested` on the Spanish one. On the French, German and Romanian requests the call ran,
matched nothing, and the reply ended with the note saying nothing was deleted, which the stored
exchange row then holds.

Two readers keep the tool on these messages. `unasked_forget` keeps it on any letter outside
English (`à`, `ß`, `Ț`), and its fact reader (`_STATES_A_FACT`) reads English only.
`forget_unrequested` (`forget_unrequested.py`) keeps it on the same letters, although its word list
already names the forget verbs and negations of all four languages. The rise itself is not
tonight's code, the llama-server build or the code since 2026-11-07: an empty recall block with
five tools calls on 14 of 20 draws, and a recalled row holding the fact on 2 of 10, where one
approved card deleted that row ([separation](../../readings/forget-calls-on-remember-rise.md)).

Reproduction: send `Merk dir, dass mein Hund Bello heißt.` in a new chat and read the proxy log
for a `forget_memories` call on the first request.

## What to do

1. In `forget_unrequested`, stop the letter clause from firing on the letters of French, German,
   Spanish and Romanian, and add the forget verbs its list lacks (`retir`, `enlev`, `quit`,
   `scoat`, `streich`) and the words for memory. Write statements that ask to forget in each
   language as tests first, with the near misses that must keep the tool.
2. Replay every recorded draw message and every test string through the old and new reader, and
   name each one that changed.

## History

- 2026-11-12: filed from the setup of the recalled memory language draws, where three of four
  requests to remember in another language ran a forget call.
