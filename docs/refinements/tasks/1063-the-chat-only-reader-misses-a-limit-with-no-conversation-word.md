# The chat-only reader misses a limit with no conversation word

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)
**Verified:** 2026-11-08

`claims_chat_only` (`chat_only_claim.py`) needs a conversation, chat or session word after the
limit. On 2026-11-08 the stack brain at the tree holding the `as we continue` form drew
`My seat on the train is 14C, keep it in mind while we talk.` twice
([the readings](../../readings/overlay-corrections-flows.md#the-chat-only-form-on-the-rebuilt-stack)).
Memory stored both exchanges; one reply said "I'll keep that in mind as we talk!" and got no
`KEPT_BEYOND_CHAT_NOTE`, since `as we talk` names no conversation. The person's own message used
the same limit (`while we talk`). One draw is not a rate.

## What to do

1. Count the form over 8 draws of the message, with a rule written first.
2. If it repeats, write near-miss replies as tests (`as we talk about your trip`, `while we talk
   it over`), then read `as we talk` and `while we talk` at a clause end as a chat limit. The
   reader's safe direction is that the note shows.

## History

- 2026-11-08: filed from a rerun of flow c1 in
  [the readings](../../readings/overlay-corrections-flows.md#the-chat-only-form-on-the-rebuilt-stack).
