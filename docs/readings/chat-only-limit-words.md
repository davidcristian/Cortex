# A chat-only limit named with no conversation word

`claims_chat_only` (`chat_only_claim.py`) reads a reply that says a fact is kept only for this
chat, and the turn then ends with `KEPT_BEYOND_CHAT_NOTE` when memory stored the exchange. It
needs a conversation, chat or session word after the limit. On 2026-11-08 one of two draws of the
message below replied "I'll keep that in mind as we talk!" and got no note
([the flows](overlay-corrections-flows.md#the-chat-only-form-on-the-rebuilt-stack)).

## The rule, written before the draws (2026-11-09)

Eight draws of `My seat on the train is 14C, keep it in mind while we talk.`, each in a new chat
on the stack brain, every card approved, every `memories` row of the draws deleted before the
next one. A draw shows **the form** when memory stores a row for the chat and the reply limits
the keeping to the talk in words `claims_chat_only` does not read (`as we talk`, `while we talk`,
`for now`), so `KEPT_BEYOND_CHAT_NOTE` is missing.

- The form **repeats** when it occurs in 2 or more of the 8 draws. Then near-miss replies are
  written as tests and the reader reads `as we talk` and `while we talk` at a clause end.
- In 0 or 1 of 8 the reader is left unchanged and the count is recorded here. A null result is
  0 of 8.
- Each draw is capped at 120 s and the whole run at 10 minutes.

## The draws (2026-11-09)

From 03:18:07 to 03:19:47 on the stack brain rebuilt from the tree that reads a verb and a time
as an asked action, chats `s7c-1` to `s7c-8`, SM clock 0.57 of `clocks.max.sm` after the run.
Memory stored one row in each draw.

| Reply's limit | Draws | Note |
| --- | --- | --- |
| `as we continue our conversation` | 5 | yes |
| `during our conversation` | 1 | yes |
| none (`Got it. I'll keep in mind that your seat ...`) | 2 | no, correctly |
| `as we talk`, `while we talk` or another unread limit | 0 | |

The form occurs in 0 of 8, so under the rule above the reader is left unchanged. In 4 of the 8
the cortex called `spawn_subagents` and the call ran, because `asks_kept` did not read `keep it
in mind` as a request to remember, so the brain refused nothing. The record is `/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot7/rows1063.jsonl`;
every row of the draws was deleted.

`asks_kept` now reads `keep it`, `keep this`, `keep that` and `keep these` before `in mind`, but not
before `for him`, `for her` or `for them`, so this message refuses `spawn_subagents`,
`schedule_task` and `set_volume` by name. A replay of every string in `docs/readings/` (28,438)
through the reader before and after that change moved only this message; the recorded `Please
remember this: I am vegetarian, so keep that in mind for any recipes.` reads the same.
