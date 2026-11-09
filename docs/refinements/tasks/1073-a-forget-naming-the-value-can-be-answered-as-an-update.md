# A forget naming the value can be answered as an update

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

On 2026-11-09, in one of 8 `n1v` draws of
[the readings](../../readings/forget-shared-number.md#the-fixed-draws-2026-11-09), the message
`Forget my gym locker number, it is 5521.` made an approved `forget_memories` call that deleted the
gym row, and the reply was `I've updated your gym locker number to 5521.` The brain appended the
note that nothing in the message was kept, but no note said the gym locker number was forgotten,
and `NUMBERS_LEFT_NOTE` was not appended, since `claims_forgotten` does not read `updated`. The
person is told neither that the fact was deleted nor that the padlock row still holds the number.
The draw's requests match the base build's, so the reader change of that night does not cause it.

## What to do

1. Write near-miss replies as tests first (`updated`, `changed`, `saved`, a question, a negation),
   and replay every recorded forget reply in `docs/readings/` through the old and new reader.
2. Try a note the brain appends when an approved forget deleted rows and the reply says no removal,
   naming how many exchanges were forgotten; a reply note shows when unsure. No `ToolResult` or
   `TaintLedger` field holds that count, so add one, which the handoff record keeps. The reply
   reader cannot be `names_removal` alone: it reads English only, and of the 49 recorded reply
   strings in `docs/readings/` that name a forget, change or save, 9 name no removal by it, among
   them `Am uitat codul.`, `Ich habe das vergessen.` and `j'ai oublié`, which do. Read the removal
   words of the note languages too, as `_REMOVED` in `numbers_left_claim.py` does.
3. Write rows and a rule into the readings, then draw `n1v` until the form occurs twice.

## History

- 2026-11-09: filed from the fixed `n1v` draws of the reader that keeps a fact the message does
  not name beside the value.
- 2026-11-09: premise checked: `names_removal` is false on the update reply, on `changed`,
  `saved`, a question and a negation, and on three recorded replies naming the removal in French,
  German and Romanian; the remedy now names the missing count field. No build in the time box.
