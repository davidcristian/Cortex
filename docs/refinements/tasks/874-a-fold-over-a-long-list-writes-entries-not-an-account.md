# A fold over a long list writes entries, not an account

**Status:** open, actionable
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-10-15

`_INSTRUCTION` asks the fold to keep every name and number a later question might depend on. On the
cortex, a 53,836-character inventory followed by no question was folded into entries until the
512-token bound stopped the reply in three of six folds, and `clean_recap` rejected them; the same
list followed by "Which bin is item 4958 in?" was folded into the answer alone in six of six,
keeping nothing else of the list
([readings](../../readings/history-recap.md#a-fold-over-a-long-list)). A rejected fold stores
`UNFOLDED_NOTE` and moves `covers`, so it costs one bounded reply rather than one per turn, but the
list is then in neither the window nor an account.

Four candidates were drawn on those rows and none passed its rule. Variant L ("describe what it holds
(its kind, how many entries, the range of its ids and dates)") made every list fold an account, but
all twelve entry counts it wrote were false, and four of six L2 recaps dropped the answer. Variant Q
("say what kind of list it is and the first and last ids or dates it shows, and give in full any
entry a message asked about") passed 11 of 18 list recaps, four of its seven misses accounts with a
false count. Variant Q2 (Q plus "Give no count of its entries unless the message states one.")
passed 14 of 18 on L1 to L3: two false counts remained and two L1 folds hit the bound. Variant T
(the tree, with the cut line naming how many lines were cut) passed 8 of 18, every L2 recap the
answer alone. All four kept P1, N2 and the head and tail fold's cut rows as the tree does, except
two of L's N2 recaps, which dropped the `503`.

One fresh row did not test what it was written for. No L4 recap of any variant named the loans,
since its lines hold no word for their kind, so B, Q2 and T all scored 0 of 6 there. On L5 the second
rule counts only an id range, and three Q2 recaps that gave the time range and the answer failed it.

## What to do

Draw variant **Q2T**, Q2's sentence with T's cut line, so the fold has a true line count beside the
rule against counting. Redraw L4 with a first line `loan_id | title | borrower | due_date` under the
heading "Library loans", for B too, and decide before the draw that on L5, whose entries have no id
of their own, a time range counts as an id range. Rows, rule and thresholds are otherwise the third
rule in the readings; the rows go in a readings file of their own, since `history-recap.md` is at
the 250-line limit.

## History

- 2026-10-15: filed from the rows of the fold over a cut message.
- 2026-10-15: drew variants L and Q on the cortex; neither passed its rule
  ([readings](../../readings/history-recap.md#a-fold-over-a-long-list)), so the next candidates and
  two fresh rows are written above.
- 2026-10-15: drew Q2, T, and B on the fresh rows
  ([readings](../../readings/history-recap.md#a-fold-over-a-long-list)); neither passed (Q2 14 of
  18 on L1 to L3 and 3 of 12 on L4 and L5, T 8 and 2, B 2 of 12), and L4 could not be passed as
  written, so the next candidate and a corrected L4 are written above.
