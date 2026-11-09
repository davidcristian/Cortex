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

On the stack brain rebuilt from that change, from 05:19:13 to 05:19:52, four draws of the message
(chats `s11k-1` to `s11k-4`, each capped at 120 s, cards approved, SM clock 0.57 of
`clocks.max.sm`) called no tool and stored one row each, every one deleted after. This shows the
change runs; it is no rule row. The record is
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot11/live.jsonl`.

## Second audit probes of keep it in mind, 2026-11-09

Unit calls (`probe3.py`, log `probe3.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot13/`).
`asks_not_kept` reads every request not to keep beside `keep it in mind`: `for now but don't save
it`, `no need to remember it`, `for this chat only, don't store it`, `but do not keep it in memory`,
`Don't write it down anywhere`, `but forget it after this chat` and `don't remember it in other
chats`, so `memory_withheld` stores none of them. `Keep it in mind for now, I'll tell you later
whether to save it.` asked for no keep and no withhold, and was stored.

`asks_not_kept` now reads a save decision the person puts off (`I'll tell you later whether to
save it`, `let me decide later whether to store it`, `I will decide tomorrow if I want you to
remember it`) as a request not to keep, while `Keep it in mind for now` alone, `I'll tell you
later what to do`, `I'll tell you later whether I remember the address` and `Did you decide
whether to save it?` still store. A replay of every string in `docs/readings/` (28,810) through
the reader before and after that change moved none.

The same decision put off in French, German, Spanish or Romanian now asks not to keep too: a first
person tell, let know or decide verb (`je te dirai`, `ich sage dir`, `te diré`, `îți spun`,
`je déciderai`, `ich entscheide`, `decidiré`, `o să decid`), then `si`, `ob` or `dacă` and a
keep verb in the same clause, as in `Merk es dir erst mal, ich sage dir später, ob du es speichern sollst.`. Each
language's bare `keep it in mind for now` form, a question whether it was saved, a later word on
something else (`je te dirai plus tard quoi faire`, `ich sage dir später, ob ich mich erinnere`,
`wo du es speichern sollst`) still store (tests in `test_memory_claim.py`). A replay of 40,188
strings (every distinct string of `docs/readings/` and every quoted string of the brain's tests)
through the reader before and after moved only the eight new test messages. Script
`replay1100.py` and log `replay1100b.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot17/`.
