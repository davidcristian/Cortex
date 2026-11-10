# A request to remember with a reminder says the fact was not saved

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-10

On 2026-11-07 the `cortexn15` stack answered
`Remember que mi hermana se llama Lucía, and remind me tomorrow at 18:00 to call her.` with a
`forget_memories` call that matched nothing, `list_scheduled`, and a `schedule_task` call stored at
18:00. The reply ended `I couldn't find any previous memory about your sister's name, so I haven't
"saved" it as a long-term memory`, while the exchange was stored as a `memories` row and is
recalled in later chats ([readings](../../readings/overlay-language-and-locale-flows.md#4-messages-in-two-languages)).

`asks_kept` reads the message, since it opens with the English `Remember`, so the language of the
request is not the cause. `unasked_forget` (`unasked_tools.py`) kept the forget tool offered for
two reasons, each enough: `Lucía` holds a letter outside English, which the reader takes as a
possible retraction, and the Spanish clause states the fact in no English form it reads (`my`,
`is`). Both fail toward keeping the tool on purpose. Only the English form with `Lucia`
(`Remember that my sister is called Lucia, and remind me ...`) has the forget tool refused. No
reader looks at a stored turn's reply for a statement that the fact was not saved: the note for a
reply that keeps a fact for this chat only (`claims_chat_only`, `chat_only_claim.py`) reads a keep
verb before "this conversation", and the claim readers in `memory_claim.py` read only claims that
something was kept.

Reproduction: send the message above in a new chat with every card approved, then read
`memories` for `Lucía`.

## What to do

1. Add a reader of a stored turn's reply that says the fact was not saved
   and append `KEPT_BEYOND_CHAT_NOTE` there, with near-miss replies as tests first ("I haven't set
   a reminder", "I didn't save the file", "I couldn't find a previous memory").
2. Replay every recorded reply through the new reader and list each change.

## History

- 2026-11-07: filed from the language and locale flows on the shared stack.
- 2026-11-07: drew the message and its English form with `Lucia` three times each on the
  rebuilt stack brain: no draw called `forget_memories` and no reply said the fact was not saved
  ([readings](../../readings/overlay-language-and-locale-flows.md#8-requests-to-remember-in-four-more-languages)),
  so the reply reader waits for a second such reply.
- 2026-11-10: the trigger fired. Two stored draws of the refused fan-out comparison replied that
  the fact was not saved: `Remember that my locker code is 4417 and remind me at 18:00 to empty the
  locker.` after a refused `forget_memories` (`I noticed I didn't save it`), and `Souviens-toi que le
  code de mon casier est 4417 et rappelle-moi demain à 9h de vider le casier.` after a forget that
  matched nothing (`je n'ai pas pu m'en souvenir`)
  ([readings](../../readings/spawn-refused-on-remember.md#the-draws-2026-11-10)).
