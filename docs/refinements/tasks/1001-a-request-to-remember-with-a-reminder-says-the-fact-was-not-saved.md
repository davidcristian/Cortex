# A request to remember with a reminder says the fact was not saved

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-07

On 2026-11-07 the `cortexn15` stack answered
`Remember que mi hermana se llama Lucía, and remind me tomorrow at 18:00 to call her.` with a
`forget_memories` call that matched nothing, `list_scheduled`, and a `schedule_task` call stored at
18:00. The reply ended `I couldn't find any previous memory about your sister's name, so I haven't
"saved" it as a long-term memory`, while the exchange was stored as a `memories` row and is
recalled in later chats ([readings](../../readings/overlay-language-and-locale-flows.md#4-messages-in-two-languages)).

The typed readers give the English form of the message the same treatment: `asks_kept` reads it,
and `unasked_forget` refuses nothing, because the message also asks for a reminder. The note for
a reply that keeps a fact for this chat only (`claims_chat_only`, `chat_only_claim.py`) does not
read "haven't saved it as a long-term memory".

Reproduction: send the message above in a new chat with every card approved, then read
`memories` for `Lucía`.

## What to do

1. Draw the message and its English form, three draws each, and count the forget calls and the
   replies that say the fact was not stored.
2. If such replies recur, widen the reply reader the note uses, with near-miss replies as tests
   first ("I haven't set a reminder", "I didn't save the file").

## History

- 2026-11-07: filed from the language and locale flows on the shared stack.
