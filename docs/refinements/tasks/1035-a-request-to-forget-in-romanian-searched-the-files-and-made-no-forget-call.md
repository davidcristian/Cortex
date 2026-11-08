# A request to forget in Romanian searched the files and made no forget call

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-08

On 2026-11-08 the cortex answered `Uită codul meu 7788.` ("forget my code 7788") on the shared stack
by calling `list_allowed_directories` and `search_files` for `7788`, and made no `forget_memories`
call. Its thinking read "uită" as possibly "look at", and its reply asked which file was meant. The
turn stored nothing, but a row already holding 7788 would have stayed. The French and German
requests drawn beside it both called the forget tool
([readings](../../readings/claim-reader-replays.md#a-forget-in-four-more-languages-and-an-english-keep-idiom-2026-11-08)).

## What to do

1. This is one draw. Write a replication into the readings first: seed a row holding 7788 in a new
   chat, then draw `Uită codul meu 7788.` and `Te rog, uită codul meu 7788.` 4 times each in new
   chats, and count the turns that leave the row.
2. If the row stays in at least 2 of 8, try the brain-appended form before any prompt wording: a note
   after a typed check that the message `asks_not_kept` and the turn made no forget call.

## History

- 2026-11-08: filed from one draw on the shared stack beside the request reader change.
  Named in [R-1007](1007-a-request-to-forget-in-another-language-answered-without-a-call-is-stored.md).
