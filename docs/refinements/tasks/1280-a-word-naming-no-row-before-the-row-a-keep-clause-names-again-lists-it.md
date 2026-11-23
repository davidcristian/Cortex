# A word naming no row before the row a keep clause names again lists it

**Status:** done 2026-11-23
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242`, `Forget the card
4242, keep only the card.` and `Forget the card 4242, keep my old card.` list the card. The first
message asks to keep it, and the second may. `_restated` (`forget_inside.py`) keeps a row named to
forget and again in a keep clause unless a word before its name in the clause names no row. That
condition deletes the card of `Forget the card 4242, I don't need the card.`, where `need` makes
the negation a request to delete, and `only` and `old` name no row either. The generator of 42,356
messages writes no such form, so its count of rows listed against the message has none of them.

## What to do

1. Write tests first: `keep only the card` keeps the card, and `I don't need the card` and `I
   don't want the card anymore` still delete it.
2. Add no word to a word list, and do not keep the row whatever stands before its name: that
   also keeps the phone of `Forget my phone but keep Anna's phone.`, where `Anna` names a stored
   row no call matched. Give `_restated` the rows the keep clause names outside the matches
   (`keep_named` in `forget_keep_named.py` finds them), so a word naming a stored row that the
   row word names too stops the keep and a word naming no stored row does not.
3. Count the rows newly kept that the message asks to delete, over the generator and every
   string of the brain's forget tests. No row may be newly listed.

## History

- 2026-11-21: filed with the change that keeps a row a keep clause names again before a word
  naming no row
  ([R-1216](1216-a-keep-clause-naming-the-row-to-forget-beside-a-word-for-only-lists-it.md)).
- 2026-11-21: replayed keeping the row whatever stands before its name. Over the generator 64
  rows were newly kept, each either way, and none newly listed. Over the 5,979 calls of the
  strings of the brain's forget tests 45 rows were newly kept in 14 calls of 7 strings, 6 of
  them messages asking to delete the row, as `Forget my phone 4242 but keep Anna's phone.` and
  `Forget the card 4242, I don't need the card.`, and 7 tests failed, among them the one in
  which a forget reports the stored row for Anna that no call matched. Left open: the fix
  needs the rows a keep clause names outside the matches, as step 2 says. The listing is
  `cmp_v2.txt` in `/home/david/.cache/cortex-run/2026-11-21/f2/`. A keep clause naming a second
  row that the row word names too lists the first:
  [R-1283](1283-a-keep-clause-naming-the-row-to-forget-and-a-second-row-its-word-names-lists-the-first.md).
- 2026-11-23: done. `may_keep` (`forget_inside.py`) now keeps a row any reading of a keep
  clause names, whatever other words the clause holds, so `keep only the card` and `keep my old
  card` keep the card. Over the generator and tonight's forms the rows asked to keep that the
  card lists went from 36 to 0, with no row newly listed and 91 rows asked to delete newly kept,
  among them `Forget the card 4242, I don't need the card.` and `Forget my phone 4242 but keep
  Anna's phone.` ([readings](../../readings/forget-keep-any-reading.md)). The forget side's longer word reading names a row through a function
  word: [R-1306](1306-a-forget-word-one-or-two-letters-longer-than-a-function-word-names-every-row-holding-it.md).
