# A request to remember spends its thinking looking for a tool to store the fact

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Verified:** 2026-11-07

The brain records every exchange at turn end and offers no tool that stores one
([ADR-0008](../../adr/ADR-0008-memory-v1.md)), and nothing the cortex reads says so. The only memory
wording in its request is the recall block ("Relevant memories from earlier conversations") and the
`forget_memories` description ("Delete from memory every remembered exchange").

On 2026-11-07 the `cortexn15` stack (gemma-4-12B at context 16,384, llama-server build
`b12169-3ed7284f2`, the SM clock at 0.57 of its maximum) drew five requests to remember over
`Converse`, each in a new chat with every card approved. Run logs `turns.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/37073e3c-5ca6-42f6-aae1-df9e67b0e4db/scratchpad/stack/logs/`
and `remember.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/37073e3c-5ca6-42f6-aae1-df9e67b0e4db/scratchpad/slot1/`.

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
([readings](../../readings/remember-request-tool-search.md#the-draws-2026-11-07)). The search is
left: base searched in 15 of 15 draws, and one system message on a turn `asks_kept` reads cut it
to 5 of 15, above the bound of 2 its rule set.

1. Write rows and a rule into that readings record before any draw: R01 to R15 on base and on two
   candidates, the same sentence at the end of the first system message, and a sentence in the
   `forget_memories` description saying memory stores every exchange by itself and the tool only
   deletes. Keep the bound of 2 of 15 and the counts of the first rule.
2. Compare the first requests of each pair before writing a rule item.

## History

- 2026-11-07: filed from the shared stack's bring-up, where the proof turn of the turn driver
  showed the search on its first request to remember.
- 2026-11-07: drew base and two candidates on R01 to R15. The note the brain appends after a typed
  check of the reply shipped; the system message on a request to remember searched in 5 of 15
  draws and did not ship.
