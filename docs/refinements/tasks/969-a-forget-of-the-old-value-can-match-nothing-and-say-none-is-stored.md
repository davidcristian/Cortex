# A forget of the old value can match nothing and say none is stored

**Status:** done 2026-11-10
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`Note that my phone number is now 0699000000, and delete the old one.`, with a row holding
`0612345678`, called `forget_memories` with a text that matched nothing in 3 of 22 draws of it and its
locker code form. The old row stays and the turn is stored, so two rows hold different numbers. Each
reply said no old value was stored, for example "I couldn't find a previous phone number to remove as
there wasn't one stored" ([draws](../../readings/claim-reader-replays.md#the-readers-in-real-turns-2026-10-31)),
since `_NONE_FOUND` (`memory_forget_chosen.py`) tells the model to say nothing about it was stored.
One more such draw said the new code "was not kept because you asked to forget something in the same
message" while a row held it
([draw](../../readings/claim-reader-replays.md#the-note-on-every-withheld-request-to-remember-the-draws-2026-10-31)).

A second form, a later call matching nothing after an earlier call of the same turn deleted the
row, now reads a result naming that delete rather than `_NONE_FOUND`
([draws](../../readings/forget-after-delete-provoked.md)).

Twenty draws on 2026-11-05 read every call text through a proxy that records the requests to the
model host ([draws](../../readings/forget-no-match-on-remember.md#a-repeated-forget-the-draws-2026-11-05)).
The unmatched first call came in 2 of them, and its text was the new number `0699000000`, which no
row holds; each reply said it could not find the old number. Over 60 draws of M02 that form came in
6, the old row stayed in each, and the replies said no old number was found or asked for it.

## What to do

1. An unmatched first call naming the new value. Its result text, on a call whose text follows
   "now" or "new" in a message that asks to forget the old value, asks for one word naming the
   fact; the
   [rows and the rule](../../readings/forget-naming-the-new-value.md#rows-and-the-rule-2026-11-07)
   are written, with a row for a value never stored, where "nothing about it was stored" is
   correct. The candidate and its near-miss tests are built and kept as a
   [patch](../../readings/forget-new-value-patch.md). Next: a row whose first request does not hold
   the old value, with its rule written first, drawn on a build of that patch.

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
- 2026-11-06: 15 more draws of M02 through the proxy on the same candidate gave 0 counted draws, 1
  of 30 against the rule's 2, so step 1's candidate is not committed and its diff is recorded as a
  patch in the readings; a row that provokes the form is the next draw. Step 2's form came in 2 of
  15 again, 6 of 60 in all, each reply saying no old number was found.
- 2026-11-07: the premise still holds in the code. A row written to ask twice for the old value,
  drawn 15 times on a build of the recorded patch, counted 7 draws, and no counted reply said the
  old number was not stored, gone or not found, so the rule passed and the result naming an
  earlier delete ships; step 2 is the one left.
- 2026-11-07: step 2's rows and rule are written, undrawn: two rows of the form, one of a value
  never stored that follows "now", and no shipped build drawn.
- 2026-11-07: the premise still holds in the code. Step 2's candidate was built with 27 tests,
  fourteen mutation rows over them all failed, and the rows were drawn through the proxy: none of
  60 N01 and N02 draws counted (every first call named the old number, which recall showed),
  and every V01 draw said nothing was stored, so the rule gave no result and the candidate is
  [recorded as a patch](../../readings/forget-new-value-patch.md) rather than committed.
- 2026-11-09: the premise still holds in the code: an unmatched first call still reads
  `_NONE_FOUND`. The note recorded for
  [R-1061](1061-a-forget-of-what-was-just-said-can-match-nothing-and-say-it-was-never-stored.md)
  does not reach this form, since no row holds the new value its call names, so one fix for both is
  not supported. Step 1's row was not drawn inside the slot's time box.
- 2026-11-10: done. The cause it shares with
  [R-1061](1061-a-forget-of-what-was-just-said-can-match-nothing-and-say-it-was-never-stored.md)
  is `_NONE_FOUND`, which tells the model to say nothing about the fact was stored. A fix for
  one call text could not meet a rule, since the text came in 0 to 2 of 24 draws.
  `UNMATCHED_FORGET_NOTE` (`forget_unfound_claim.py`) now follows every turn whose forget
  matched nothing and removed no row: nothing was deleted, and an exchange stating the fact in
  other words is still stored. It reads no reply, its unit tests include this form, and all 7
  turns that reached it on purpose ended with it ([readings](../../readings/forget-matched-nothing-note.md)). The result text is [R-1109](1109-the-no-match-forget-result-tells-the-model-to-say-nothing-was-stored.md).
