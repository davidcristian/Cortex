# A forget of everything keeping a row in words no reader reads makes no forget call

**Status:** done 2026-11-27
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

Drawn on the stack brain over four stored rows
([readings](../../readings/forget-everything-unread-role.md#drawn-after-the-card-changes-2026-11-15)):
`Forget everything, my card stays.` and `Uită tot în afară de card.` made no forget call in 4 of
4 draws, and each reply said the other memories were cleared or that only the card was stored.
The first request held the card row alone: recall ranked it, and `with_forget_reach`
(`forget_reach.py`) adds the nearest rows only beside a keep clause that
`asks_to_forget_keeping` reads. Each reply ended with a true note that nothing was deleted
(`UNFORGOTTEN_CLAIM_NOTE` or `UNCALLED_FORGET_NOTE`), so the person is not misled, and the rows
asked to delete stay stored. The first note's advice, to ask again in a message of its own,
gives the same turn again. A call would not help: the card keeps every row of the English
message, and for the Romanian one a call naming `card` lists the card, since `tot` is unread
(filed with the other unread words for all).

## What to do

1. The draw with the rows and pass rule written first was taken on 2026-11-24, and the premise
   holds ([readings](../../readings/forget-everything-unread-forms.md#drawn-on-the-stack-brain-2026-11-24)).
2. Append a typed note that is true on every turn it reaches: when `everything`
   (`forget_permit.py`) reads the message, its unread words name a stored row and no forget call
   of the turn deleted a row, name a form the card reads, as `Forget everything but my card.`
3. Leave the first request as it is for this form while the card keeps every row under it: each
   call would return `KEPT_ALL`.

## History

- 2026-11-15: filed from the audit draws of the day's card changes.
- 2026-11-23: checked the code side through `ForgetChosenTool`. `Forget everything, my card
  stays.` still keeps every row for the call texts `card` and `4242`, and `Uită tot în afară de
  card.` still lists the card (R-1230). The form the note of step 2 names works as it says:
  `Forget everything but my card.` keeps the card for the text `card` and deletes the locker code
  for `locker` or `4242` and the phone for `phone`. No forget reader of `forget_reach.py`,
  `forget_uncalled.py` or `forget_claim.py` changed since 2026-11-15. The live draw of step 1 was
  not taken, since the slot did no card work. Left open.
- 2026-11-24: drew both messages 4 times each on the stack brain of this date, with the pass rule
  written first ([readings](../../readings/forget-everything-unread-forms.md#drawn-on-the-stack-brain-2026-11-24)).
  No draw made a forget call, the turn's request held the card row alone in all 8, and every
  reply ended with a true note that nothing was deleted. 6 replies claimed a delete and 2 a
  fresh start or a cleared context. The 3 rows asked to delete stayed stored in each draw, and
  the card too. The premise holds, so step 2 is the next step. Left open.
- 2026-11-26: meets the bar of the freeze of the forget message readers ([ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md) decision 7): it rests on 8 live draws of `Forget everything, my card stays.` and `Uită tot în afară de card.` on the stack brain, and its remedy is a note true on every turn it reaches, built on the readers as they stand.
- 2026-11-27: done. `EVERY_KEPT_NOTE` (`forget_every_kept.py`) closes the reply when one word
  after the word for all names a stored row in a role no reader reads and no forget of the turn
  deleted a row. It says nothing was deleted and names a form built from the message's own words,
  as `Forget everything but my card.`, in place of `UNFORGOTTEN_CLAIM_NOTE`,
  `UNCALLED_FORGET_NOTE`, `REFUSED_HELD_NOTE` and `UNMATCHED_FORGET_NOTE`, so no note gives the
  advice that repeats the turn. Through `ForgetChosenTool` the form keeps the card and deletes
  each other row in English and French; in German, Spanish and Romanian it keeps every row, so
  the note is written in English and French only
  ([readings](../../readings/forget-everything-unread-forms.md#the-note-naming-a-form-the-card-reads-2026-11-27)).
  A message whose unread words name two rows gets the older notes. No reader was widened.
