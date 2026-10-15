# A fold over a long list is rejected every turn

**Status:** open, actionable
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-10-15

`_INSTRUCTION` asks the fold to keep every name and number a later question might depend on. Over
30,000 characters of pasted planning notes, mostly lines naming an owner and an item number, 10 of
12 folds on the cortex on 2026-10-15 listed item numbers until the reply passed `RECAP_MAX` or the
512-token bound, and `clean_recap` rejected them
([readings](../../readings/history-recap.md#a-message-cut-by-the-fold)). With the head and tail
cut that shipped from those rows, none of six folds of the same notes was rejected, but there the
fold saw a last line moving the launch date and wrote a short account around it; a list with no
such line is untested. A rejected fold stores no
recap and leaves `covers` where it was, so every later turn sends the same fold again and generates up
to its bound before the reply starts, and the pasted message is in neither the window nor an
account.

## What to do

Write rows first: pastes of lists (item numbers, a CSV, an inventory) and a control of plain notes,
with a pass rule that the fold is accepted and keeps the facts a later question needs. Then weigh
an instruction sentence that asks for a summary of a long list rather than its entries, against
storing a short fallback account when a fold is rejected, so the same fold is not sent every turn.

## History

- 2026-10-15: filed from the rows of the fold over a cut message.
