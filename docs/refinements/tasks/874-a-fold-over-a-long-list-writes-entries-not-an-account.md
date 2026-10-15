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

Draw these rows as the cut-fold rows were drawn (fold prompts from `build_recap_messages` over
`fold_slice`, sent straight to the cortex server with `RECAP_BOUNDS`), six recaps per row and
variant, and copy the rows and the rule into the readings before the first draw.

- **L1**: the 53,836-character inventory from the readings, followed by no question.
- **L2**: the same inventory followed by "Which bin is item 4958 in?".
- **L3**: a CSV of about 30,000 characters (order id, customer, amount, date) and no question.
- **P1**: the N1 chat of the cut-fold rows, as the control.

Variant **B** is the tree. Variant **L** adds one sentence to `_INSTRUCTION` after "Drop
pleasantries and repetition.": "When a message holds a long list or table, describe what it holds
(its kind, how many entries, the range of its ids and dates) and keep only the entries a message
asked about, rather than listing its entries."

Pass rule. A list recap passes when `clean_recap` accepts it and it names the list's kind and at
least one id range or entry count from the part read; an L2 recap must also give bin B-34. A P1
recap passes under the N1 rule of the cut-fold rows. L ships when it passes at least 15 of its 18
list recaps, B passes at most 9 of 18, and L's P1 passes are no fewer than B's.

## History

- 2026-10-15: filed from the rows of the fold over a cut message.
