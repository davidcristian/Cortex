# A request to remember in another language is not read as one

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-07

`asks_kept` (`memory_request.py`) reads only English. Every check keyed on it skips a request to
remember in another language: the refusal of unasked tools and sidecar tools
(`unasked_tools.py`), the refusal of an unasked forget, and the unmatched-forget case of
`memory_withheld`. On 2026-11-07 the `cortexn15` stack ran `spawn_subagents` on
`Souviens-toi que le code de mon casier à la piscine est 7731.` and on
`Merk dir, dass mein Hund Bello heißt.`, adding a delegated run to each turn, while the brain
refused the same call on the English `Remember that Ștefan owes me 12,50 € for the pizza.`
([readings](../../readings/overlay-language-and-locale-flows.md#6-requests-in-other-languages-and-the-english-readers)).

`asks_not_kept` reads a negative imperative in French, German, Spanish and Romanian since the same
night, so a request not to keep is withheld in those languages; this task is the positive form.

Reproduction: send `Merk dir, dass mein Hund Bello heißt.` in a new chat and read the brain's
`tool.invocation` audit lines: `spawn_subagents` runs.

## What to do

1. `asks_kept` controls refusals, so widening it fails away from keeping a tool. Write near-miss
   statements in each language first ("je me souviens de lui", "ich merke mir Namen schlecht",
   "recuerdo que", "îmi amintesc"), then the imperative forms ("souviens-toi que", "retiens que",
   "merk dir", "recuerda que", "ține minte că", "amintește-ți că"), as tests before the code.
2. Replay every recorded message through the old and new reader, and draw the four requests to
   remember of the readings, three draws each, counting the tool calls that run.

## History

- 2026-11-07: filed from the language and locale flows on the shared stack.
