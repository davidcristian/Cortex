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

Two instruction sentences were drawn on those rows and neither passed its rule. Variant L ("describe
what it holds (its kind, how many entries, the range of its ids and dates)") made every list fold an
account, but all twelve entry counts it wrote were false, and four of six L2 recaps dropped the
answer. Variant Q ("say what kind of list it is and the first and last ids or dates it shows, and
give in full any entry a message asked about") kept the answer in four of six L2 recaps, and four of
its seven misses were accounts with a false count. Both kept the uncut chat, the short log and the
head and tail fold's cut rows as the tree does, except two of L's N2 recaps, which dropped the `503`.

## What to do

Draw the next candidate on the same rows (L1 to L3, P1, N2, C1 to C3, as the readings define them),
plus two fresh lists so the pick is not fitted to these three: **L4**, a list of about 40,000
characters of library loans (loan id, title, borrower, due date) and no question; **L5**, a list of
about 25,000 characters of sensor readings (sensor id, time, value) followed by a question about one
reading near its end. Six recaps per row; draw B on L4 and L5 too. Copy the rows and the rule into
the readings before the first draw.

- Variant **Q2**: Q plus "Give no count of its entries unless the message states one."
- Variant **T**, the typed alternative to a prompt rule: the tree's instruction, with the line
  `_cut_middle` writes also naming how many lines were cut, so the fold has a true number to use.

Pass rule: the readings' second rule (a false entry count fails), with an L5 recap also giving the
reading asked about. A variant ships when it passes at least 15 of 18 on L1 to L3 and 10 of 12 on
L4 and L5, B passes at most 6 of 12 on L4 and L5, its P1 and N2 passes are no fewer than B's, and it
keeps at least 15 of 18 C recaps; between two that ship, the one with more list passes wins, and on
a tie T.

## History

- 2026-10-15: filed from the rows of the fold over a cut message.
- 2026-10-15: drew variants L and Q on the cortex; neither passed its rule
  ([readings](../../readings/history-recap.md#a-fold-over-a-long-list)), so the next candidates and
  two fresh rows are written above.
