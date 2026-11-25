# A request to remember spends its thinking looking for a tool to store the fact

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Verified:** 2026-11-25

The brain records every exchange at turn end and offers no tool that stores one
([ADR-0008](../../adr/ADR-0008-memory-v1.md)), and nothing the cortex reads says so. The only memory
wording in its request is the recall block ("Relevant memories from earlier conversations") and the
`forget_memories` description ("Delete from memory every remembered exchange").

On 2026-11-07 the `cortexn15` stack (gemma-4-12B at context 16,384, llama-server build
`b12169-3ed7284f2`, the SM clock at 0.57 of its maximum) drew five requests to remember over
`Converse`, each in a new chat with every card approved. Run logs `turns.jsonl` in
`stack/logs/` in the scratch directory of the 2026-11-07 run
and `remember.jsonl` in
the `slot1` scratch directory of the 2026-11-07 run.

| Message | Trace characters | Tool the trace looked for | Reply limits the fact to this chat |
| --- | --- | --- | --- |
| `Remember that my bike lock code is 4512.` | 5,365 | `remember_memory`, `save_memory` | no |
| `Please remember this: my daughter is allergic to peanuts.` | 5,260 | `add_memory`, `remember_memories` | yes |
| `Remember that my dentist appointment is on the 14th.` | 1,827 | `add_memory`, `save_memory` | no |
| `Keep in mind that my car is a blue Fiat.` | 1,011 | `remember_fact`, `remember_memories` | yes |
| `Remember that my wifi password is on the router label.` | 2,554 | `remember_memory` | no |

Three other turns on the same stack that night, a greeting, a volume question and a delegated poem,
had traces of 847, 280 and 572 characters. Every one of the five traces named a tool that does not
exist and searched the tool list for it before deciding to reply. No draw called a tool, and every
exchange was stored. Two replies said the fact was kept "for our conversation", which tells the
person the opposite of what the brain does: the exchange is recalled in every later chat.

The trace is time before the first word on every request to remember. One trace also reasoned
that a forget tool implies a remember tool, so the `forget_memories` calls on requests to remember
in [side-effect-tools-on-remember.md](../../readings/side-effect-tools-on-remember.md) may come
from the same search. That is an assumption no row has tested.

## What to do

A reply that keeps the fact for this chat only now ends with `KEPT_BEYOND_CHAT_NOTE`
([readings](../../readings/remember-request-tool-search.md#the-draws-2026-11-07)). Sentences in the
request did not stop the search: one system message on a turn `asks_kept` reads cut it to 5 of 15,
and the same sentence in the first system message or in the `forget_memories` description to 14
and 13 of 15.

A built-in whose result says the exchange is stored at turn end passed its rule on 2026-11-25 under
two names: a search in 0 of 15 draws against 15 of 15 on base, a median trace of 153 and 137
characters against 1,972, every draw calling it, no `forget_memories` call against 10 of 15, and
every fact stored ([readings](../../readings/remember-request-tool-search.md#a-tool-whose-result-says-the-exchange-is-stored-the-draws-2026-11-25)).
The candidate lives only in that run's scratch core; nothing shipped.

The tool's name is the user's pick. The proposal, one verb and object like the other built-ins:

| Name | Why | Drawn |
| --- | --- | --- |
| `remember_memories` (recommended) | The pair of `forget_memories`: the same object with the opposite verb, so the list reads as one pair | C1, passed |
| `remember` | The person's own verb, and the name base traces looked for most (11 of 15 draws) | C2, passed |
| `save_memory` | The other name the traces looked for (5 of 15), but it says the call saves, which it does not | not drawn |

1. The user picks the name.
2. Build it with tests behind `BuiltinTool`. Its result must be true on every turn it reaches, so
   `ToolOffer` offers it only on turns memory will store, and under `CORTEX_MEMORY_SCOPE=session`
   its text says later chats do not recall the exchange. It marks its argument private, since a
   fact can be a code. Edit [ADR-0008](../../adr/ADR-0008-memory-v1.md), which offers no such
   tool, and the memory module doc.
3. Draw R01 to R15 again on the built tool, with the rule above, plus the request-to-remember rows
   of [side-effect-tools-on-remember.md](../../readings/side-effect-tools-on-remember.md) that
   counted `forget_memories` calls.

## History

- 2026-11-07: filed from the shared stack's bring-up, where the proof turn of the turn driver
  showed the search on its first request to remember.
- 2026-11-07: drew base and two candidates on R01 to R15. The note the brain appends after a typed
  check of the reply shipped; the system message on a request to remember searched in 5 of 15
  draws and did not ship.
- 2026-11-07: drew the sentence at the end of the first system message and in the
  `forget_memories` description; both searched in at least 13 of 15 draws and neither ships.
- 2026-11-07: in the language and locale flows, two of four requests to remember in French,
  German, Spanish and Romanian ended the search with a `spawn_subagents` call that ran, since
  `asks_kept` reads only English; the brain refused the same call on two English requests
  ([readings](../../readings/overlay-language-and-locale-flows.md#1-the-tools-in-four-languages)).
- 2026-11-09: four of twelve English first turns `My locker code at the pool is 7319.`, a statement
  with no request word, called `spawn_subagents` to store the fact, and each call ran; one French
  first turn asked for a subagent role that does not exist
  ([readings](../../readings/forget-what-was-just-said.md#the-draws-of-the-start-hash-and-the-candidate-2026-11-09)).
- 2026-11-23: counted again on R01 to R15 with the cortex of today's compose defaults: a search in
  15 of 15 draws, median trace 2,819 characters, no chat-only reply, every fact stored. 8 of 15
  draws called `forget_memories`, and the typed refusal answered each call, which sends no event
  ([readings](../../readings/single-draw-recounts.md#the-search-for-a-store-tool-counted-again)).
  Step 1 is unchanged.
- 2026-11-25: drew base and a built-in whose result says the exchange is stored, named
  `remember_memories` and `remember`, on R01 to R15. Both passed the rule written first: no search,
  a trace under a tenth of base's median and no `forget_memories` call. The name is proposed above
  for the user's pick.
