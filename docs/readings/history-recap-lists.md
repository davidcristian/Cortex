# Readings: history recap over long lists

The fourth draw of the fold over a long list. The rows L1 to L3, P1, N2 and C1 to C3, variant B,
and the three earlier rules and draws are in
[history recap](history-recap.md#a-fold-over-a-long-list); this record holds the fourth rule and
the draw made on it.

## The fourth rule

**2026-10-16**, written before the draw. The same cortex (gemma-4-12B, `--ctx-size 16384`, the
server's sampling at temperature 1.0) and method: fold prompts from `build_recap_messages` over
`fold_slice`, sent straight to the cortex server with `RECAP_BOUNDS`, six recaps per row and
variant.

Rows. L1 to L3, L5, P1, N2 and C1 to C3 are the third rule's. **L4** is redrawn: the same 689
loans under a first line "Library loans" and a second line `loan_id | title | borrower | due_date`,
40,082 characters. Its fold reads loans L-50001 to L-50206 (the last one in part) and L-50621 to
L-50689, due 2026-10-16 to 2026-11-01 and 2026-12-06 to 2026-12-11. L5's fold reads the readings
taken on 2026-10-14 from 06:00 to 09:30 and from 12:20 to 13:30, and the question.

Variants. **B**: the tree, drawn on L4 and L5; its P1 and N2 passes are the first draw's, 6 and 6.
**Q2T**: Q2's two sentences added after "Drop pleasantries and repetition." ("When a message holds
a long list or table, say what kind of list it is and the first and last ids or dates it shows, and
give in full any entry a message asked about, rather than listing the rest. Give no count of its
entries unless the message states one.") with T's cut line, which also names the lines cut
("[37836 characters (605 lines) from the middle of this message were cut here and were not
read.]"). Q2T is drawn on L1 to L5, P1, N2 and C1 to C3.

Pass rule. The third rule holds, with three additions:

- On L5, whose readings have no id of their own, a time range counts as an id range when both its
  ends are times of readings in the part read. A range of sensor ids counts as before.
- A count of the lines or characters cut that restates the cut line is neither an entry count nor a
  false count; one that misstates it is a false count.
- A count of lines is scored as an entry count. A count is true when it equals the entries or the
  lines of the part read or of the whole list, with an entry read only in part counted or not;
  "about N" is true within 5 percent, and "over N" when the real number is larger.

Thresholds are the third rule's. Q2T ships with at least 15 of 18 on L1 to L3 and 10 of 12 on L4
and L5, B at most 6 of 12 on L4 and L5, P1 and N2 passes no fewer than B's, and at least 15 of 18
C recaps under the second rule of [the cut message rows](history-recap.md#a-message-cut-by-the-fold).

What it decides. If Q2T ships, its sentences and cut line replace the tree's `_INSTRUCTION` and
`_cut_middle` line. If it does not, no sixth wording is drawn: five candidates (L, Q, Q2, T and
Q2T) will have failed. A null result is Q2T under either list threshold, meaning a true line count
beside the rule against counting neither stops false counts nor makes the loans nameable.

## The fourth draw

**2026-10-16**, scored by hand against the fourth rule (six recaps per row; B's P1 and N2 are the
first draw's):

| Variant | L1 | L2 | L3 | L4 | L5 | L1 to L3 | L4 and L5 | P1 | N2 | C1 to C3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B | not drawn | not drawn | not drawn | 6 | 5 | not drawn | 11 of 12 | 6 | 6 | not drawn |
| Q2T | 3 | 6 | 6 | 6 | 5 | 15 of 18 | 11 of 12 | 6 | 6 | 18 of 18 |

Q2T does not ship. It meets each of its own thresholds, but B passes 11 of 12 on L4 and L5 against
at most 6. Under the heading, every B L4 recap named the loans and an id range; five named the cut
between L-50206 and L-50621, and for one of them that was the only range given. B's L5 miss gave
the sensors and the time range without 23.87. Q2T's four list misses: two L1 folds listed entries
until the bound stopped them and `clean_recap` rejected them, and two recaps gave the cut line's
line count as the list's size ("605 entries" on L1, "206 lines of data" on L5). Every Q2T L2 recap
described the list and gave B-34, every L4 recap gave L-50001 to L-50689, every P1 recap kept the
five facts with no cut claimed, every N2 recap named the `503`, and every C recap gave the `503` or
the 12 November move.

Across the four draws, the L1 folds that `clean_recap` rejected after listing entries up to the
bound were 3 of 6 for B, none for L and Q, and 2 of 6 for Q2, T and Q2T. L and Q wrote false
counts instead: all twelve of L's L1 and L3 recaps, and four of Q's list recaps.
Method: `measurements/overlay-long-input-2026-10-16/list-recap-fourth/` (`draw.py` with the
`s15.py` and `s10.py` it loads, `readpart.py`, `score.py`, `run.sh`, `draw.jsonl`, `clock.log`);
the SM clock read 0.59 of its maximum while the cortex was busy.
