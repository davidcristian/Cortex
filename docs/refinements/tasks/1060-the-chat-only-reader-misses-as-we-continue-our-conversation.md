# The chat-only reader misses "as we continue our conversation"

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)
**Verified:** 2026-11-08

`claims_chat_only` (`chat_only_claim.py`) reads a keep word followed by `for`, `during`, `in`,
`throughout`, `within`, `until the end of`, `while` or `as long as` and then `this`, `our` or `the`
conversation. On 2026-11-08, flow c1 of [the readings](../../readings/overlay-corrections-flows.md)
sent `My seat on the train is 14C, keep it in mind while we talk.`; memory stored the exchange,
and the reply said "I'll keep that in mind as we continue our conversation!" with no
`KEPT_BEYOND_CHAT_NOTE`, because `as we continue` is not in the list. The French flow c2, whose
reply said `pour la suite de notre conversation`, got the note.

## What to do

1. Write near-miss replies first as tests (`as we continue`, `as we go on`, `while we talk`, and a
   reply that names the conversation with no keep word), then widen `_CHAT` to read them. The
   reader's safe direction is that the note shows.
2. Replay every recorded reply of the chat-only draws through the old and new reader.

## History

- 2026-11-08: filed from flow c1 in [the readings](../../readings/overlay-corrections-flows.md).
