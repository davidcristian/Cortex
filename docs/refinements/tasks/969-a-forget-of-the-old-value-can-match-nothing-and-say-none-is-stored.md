# A forget of the old value can match nothing and say none is stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-06

`Note that my phone number is now 0699000000, and delete the old one.`, with a row holding
`0612345678`, called `forget_memories` with a text that matched nothing in 3 of 22 draws of it and its
locker code form. The old row stays and the turn is stored, so two rows hold different numbers. Each
reply said no old value was stored, for example "I couldn't find a previous phone number to remove as
there wasn't one stored" ([draws](../../readings/claim-reader-replays.md#the-readers-in-real-turns-2026-10-31)),
since `_NONE_FOUND` (`memory_forget_chosen.py`) tells the model to say nothing about it was stored.
One more such draw said the new code "was not kept because you asked to forget something in the same
message" while a row held it
([draw](../../readings/claim-reader-replays.md#the-note-on-every-withheld-request-to-remember-the-draws-2026-10-31)).

A second form was drawn on 2026-11-05
([draws](../../readings/forget-no-match-on-remember.md#the-texts-of-the-forget-calls-on-a-new-value-2026-11-05)):
the turn called the forget twice with the old value. The first call's card deleted the row, the
second call matched nothing, and the reply said the old number "appears it was already gone". The
no-match result is true of the store when the second call runs and false of the turn.

Twenty more draws on 2026-11-05 read every call text through a proxy that records the requests to
the model host ([draws](../../readings/forget-no-match-on-remember.md#a-repeated-forget-the-draws-2026-11-05)).
The unmatched first call came in 2 of them, and its text was the new number `0699000000`, which no
row holds; each reply said it could not find the old number. In 4 more, a call with the new number
followed the delete and matched nothing, and one reply then said no previous number was found to
delete. A repeat of the deleting call's own text came in 1 of 30 draws.

## What to do

1. A call that matches nothing after an earlier call in the same turn deleted something gets a
   result naming that delete, not `_NONE_FOUND`, whatever its text. `ForgetChosenTool` keeps the
   turn ids whose card ran a delete, bounded as `_shown` is. The repeated text alone, as the
   [rule](../../readings/forget-no-match-on-remember.md#a-repeated-forget-rows-and-the-rule-2026-11-05)
   named it, reached 1 of 30 draws and none of the 20 drawn for it. The wider form's
   [rule](../../readings/forget-no-match-on-remember.md#a-forget-after-a-delete-rows-and-the-rule-2026-11-06)
   needs 2 counted draws of 15; the first 15 gave 1, so 15 more decide it. The candidate's diff and
   its seven tests are kept beside the run logs the readings name.
2. An unmatched first call naming the new value. Write rows and a rule for a result text, on a call
   whose text the message states after "now" or "new", that asks for one word naming the fact.
   `_NONE_FOUND` is shared with a forget of a value never stored, where "nothing about it was stored"
   is correct, so both rows are drawn.

## History

- 2026-10-31: filed from the draws of the fixed readers of
  [R-967](967-a-request-to-remember-a-new-value-and-forget-the-old-one-keeps-neither.md).
- 2026-11-05: the premise holds in the code: a run that matches nothing returns `_NONE_FOUND` with no
  card, and `_unmatched_keep` (`memory_claim.py`) stores the turn when every forget call matched
  nothing and `asks_kept` reads the message. Ten draws of M02 read every call text, found the
  repeated forget, and found no unmatched first call; the first step and its rule are written.
- 2026-11-05: corrected. The candidate for the repeated text was built and drawn 20 times through
  the proxy: no draw repeated the deleting text, so its rule gave no result and it was not committed.
  The draws found the unmatched first call naming the new number, and a later call naming it after a
  delete; both steps now name those forms.
- 2026-11-06: the premise still holds in the code. Step 1's candidate was built with seven tests,
  seven mutation rows over them all failed, and 15 draws of M02 through the proxy, with the seed row
  written again, gave 1 counted draw (a later call naming the new number read the new result, and
  the reply said the old number was forgotten) against the rule's 2: no result, so the candidate is
  not committed and 15 more draws decide it. Two first calls named the new number again, step 2's
  form; one of those replies asked for the old number.
