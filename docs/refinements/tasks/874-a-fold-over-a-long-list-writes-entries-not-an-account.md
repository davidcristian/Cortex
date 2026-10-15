# A fold over a long list writes entries, not an account

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
fold saw a last line moving the launch date and wrote a short account around it. On the real shell
a 53,836-character inventory followed by no question was folded into entries until the bound
stopped it, and rejected; the same list followed by a question was folded into one sentence
answering it, keeping nothing else of the list
([readings](../../readings/history-recap.md#a-rejected-fold-over-a-list)). A rejected fold stores
`UNFOLDED_NOTE` and moves `covers`, so it costs one bounded reply rather than one per turn, but the
list is then in neither the window nor an account.

## What to do

Write rows first: pastes of lists (item numbers, a CSV, an inventory) with and without a question
after them, and a control of plain notes, with a pass rule that the fold is accepted and keeps the
facts a later question needs. Then weigh an instruction sentence that asks for an account of what a
long list holds (its kind, its size, its ranges and any entry a message singled out) rather than
its entries.

## History

- 2026-10-15: filed from the rows of the fold over a cut message.
