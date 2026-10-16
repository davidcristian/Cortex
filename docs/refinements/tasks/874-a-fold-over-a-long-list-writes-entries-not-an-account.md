# A fold over a long list writes entries, not an account

**Status:** declined 2026-10-16
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

`_INSTRUCTION` asks the fold to keep every name and number a later question might depend on. On the
cortex, a 53,836-character inventory followed by no question was folded into entries until the
512-token bound stopped the reply in three of six folds, and `clean_recap` rejected them; the same
list followed by "Which bin is item 4958 in?" was folded into the answer alone in six of six,
keeping nothing else of the list
([readings](../../readings/history-recap.md#a-fold-over-a-long-list)). A rejected fold stores
`UNFOLDED_NOTE` and moves `covers`, so it costs one bounded reply rather than one per turn, but the
list is then in neither the window nor an account.

Five candidates were drawn on those rows and none passed its rule. Variant L ("describe what it
holds (its kind, how many entries, the range of its ids and dates)") made every list fold an
account, but all twelve entry counts it wrote were false, and four of six L2 recaps dropped the
answer. Variant Q ("say what kind of list it is and the first and last ids or dates it shows, and
give in full any entry a message asked about") passed 11 of 18 list recaps, four of its seven misses
accounts with a false count. Variant Q2 (Q plus "Give no count of its entries unless the message
states one.") passed 14 of 18 on L1 to L3: two false counts remained and two L1 folds hit the
bound. Variant T (the tree, with the cut line naming how many lines were cut) passed 8 of 18, every
L2 recap the answer alone. Variant Q2T (Q2's sentences with T's cut line) passed 15 of 18 on L1 to
L3 and 11 of 12 on L4 and L5, but once the loan list had a heading the tree also passed 11 of 12
there ([readings](../../readings/history-recap-lists.md)); two Q2T L1 folds still hit the bound, and
two recaps gave the cut line's line count as the list's size. All five kept P1, N2 and the head and
tail fold's cut rows as the tree does, except two of L's N2 recaps, which dropped the `503`.

Declined on 2026-10-16 (History). The tree already describes a long list whose heading or lines
name its kind: every B recap of the redrawn L4 did, and five of six on L5 gave the answer beside
the description. On a bare list followed by no question no wording changed the result: two or three
of six folds listed entries until the bound under the tree, Q2, T and Q2T alike, the two wordings
that stopped the listing (L and Q) wrote false counts instead, and Q2T's true line count was misread
as the list's size twice. Such a fold is rejected, which stores `UNFOLDED_NOTE` and costs one
bounded reply, and memory records the paste with its exchange. On L2 the tree's account is the
answer alone, which is what the conversation asked, and no 2,000-character account keeps the
entries of an 860-line list. A note built in code, naming the message's line count and quoting its
first and last lines, was the structural alternative considered; it would give a later question no
entry it needs, so it is not filed.

## History

- 2026-10-15: filed from the rows of the fold over a cut message.
- 2026-10-15: drew variants L and Q on the cortex; neither passed its rule
  ([readings](../../readings/history-recap.md#a-fold-over-a-long-list)), so the next candidates and
  two fresh rows are written above.
- 2026-10-15: drew Q2, T, and B on the fresh rows
  ([readings](../../readings/history-recap.md#a-fold-over-a-long-list)); neither passed (Q2 14 of
  18 on L1 to L3 and 3 of 12 on L4 and L5, T 8 and 2, B 2 of 12), and L4 could not be passed as
  written, so the next candidate and a corrected L4 are written above.
- 2026-10-16: drew Q2T, and B on the redrawn L4 and on L5, on a rule written first
  ([readings](../../readings/history-recap-lists.md)). Q2T passed 15 of 18 on L1 to L3 and 11 of 12
  on L4 and L5, and B 11 of 12 on L4 and L5 against at most 6, so Q2T does not ship; declined on
  the evidence of all five candidates, with no new task filed.
