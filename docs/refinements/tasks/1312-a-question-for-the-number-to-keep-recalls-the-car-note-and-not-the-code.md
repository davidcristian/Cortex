# A question for the number to keep recalls the car note and not the code

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-11-23

On 2026-11-23 the store held two exchanges, `Keep in mind that my car is a blue Fiat.` and
`Remember that my gym locker code is 5819.`, and a new chat asked `Reply with only the number:
which number did I ask you to keep?`. The `judge` rank saw both notes in all five draws and never
picked the code: it returned the car note alone in four and `{"order": []}` in one. Every reply then
said no number was asked for, or answered `None`, and that exchange was stored as a row, so a later
chat can recall a row saying no number was kept
([readings](../../readings/single-draw-recounts.md#a-recall-question-that-finds-no-value)). The
2026-11-07 draw of the same question also recalled the car note.

## What to do

1. Send the recorded judge request (line 14 of
   `~/.cache/cortex-run/2026-11-23/s5/proxy/log/requests.jsonl`) to the cortex 20 times at the
   judge's own settings, and count the orders that hold the code note, to tell a constant miss from
   a draw-to-draw one.
2. If the code note is picked in fewer than half, add the two notes and the question to the judge's
   quality corpus (`recall_corpus.py`) and write a rule in
   [ranked recall](../../readings/ranked-recall.md) before any change to the judge's prompt.

## History

- 2026-11-23: filed from the recount of task 1005, whose loop and invented value did not recur.
