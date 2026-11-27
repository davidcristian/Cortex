# A question for the number to keep recalls the car note and not the code

**Status:** done 2026-11-27
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

On 2026-11-23 the store held two exchanges, `Keep in mind that my car is a blue Fiat.` and
`Remember that my gym locker code is 5819.`, and a new chat asked `Reply with only the number:
which number did I ask you to keep?`. The `judge` rank saw both notes in all five draws and never
picked the code: it returned the car note alone in four and `{"order": []}` in one. Every reply then
said no number was asked for, or answered `None`, and that exchange was stored as a row, so a later
chat can recall a row saying no number was kept
([readings](../../readings/single-draw-recounts.md#a-recall-question-that-finds-no-value)). The
2026-11-07 draw of the same question also recalled the car note.

## What to do

1. The recorded judge request, sent 20 times on 2026-11-27, held the code note in 0 of 20 orders,
   and the same case through `JudgeRecallPolicy` in 0 of 20
   ([readings](../../readings/ranked-recall.md#a-number-asked-to-keep-over-stored-exchanges)), so
   the miss is constant. The case is the first `EXCHANGES` entry of `recall_corpus.py`. Draft a
   change to the judge's instruction or note format that picks the code note, and keep it only
   when it passes the rule in that section: the asked note in at least 10 of 20 draws of
   `test_rerank_judge_exchanges_live.py`, and the wide corpus's judge column kept.

## History

- 2026-11-23: filed from the recount of task 1005, whose loop and invented value did not recur.
- 2026-11-27: the count and the corpus entry done (0 of 20 orders held the code note on the
  replay), the rule written in the ranked recall readings; narrowed to the judge change.
- 2026-11-27: done. Of three changes written down before the first draw, the instruction alone
  held the code note in 0 of 20 draws, the question after the notes in 6, and both in 17 and
  then 18; the two together kept the wide corpus's judge column and ship. On the deep model the
  change drew 24 of 26 on the wide corpus, the count of the old prompt, and held the code note in
  19 of 20 draws ([readings](../../readings/ranked-recall.md#a-number-asked-to-keep-over-stored-exchanges)).
