# A forget of every value except one kind keeps a row of another kind

**Status:** done 2026-11-15
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

With the rows `Remember that my locker code is 4242.`, `Retiens que ma carte est 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, the call text `4242` and the message
`Forget every 4242 except the card.`, the forget card lists only the locker row. It keeps the phone
row, which holds `4242` as the last group of a longer value, though the message asks for every
value but the card. The kept note names the phone row, so the person sees it, and keeping is the
card's safe direction. The start build `cec7c748f` and HEAD `c0e02329e` do the same. The probe is
`probe.py` with `cases2.json` in
the `slot10` scratch directory of the 2026-11-13 run.

## What to do

1. Write tests first: the message above lists the locker and phone rows and keeps the card row;
   `Forget 4242, except the card.` still lists only the locker row.
2. Read a word for all (`quantifies` in `forget_unnamed.py`) beside a keep clause as asking for
   every row the keep clause does not name, including a last group of a longer value.
3. Replay every recorded message and test string through the card.

## History

- 2026-11-13: filed by the first audit of the night.
- 2026-11-15: done with a narrower shape than step 2. Listing every row the keep clause does
  not name deleted a `Handy` row for `Forget every 4242 except the phone.` in the replay, so a
  last group is listed only when each word of the keep clause is a kind word of the table and the
  row names another kind of it. The message lists the locker and phone rows and keeps the card;
  `Forget 4242, except the card.` lists only the locker row. The replay changed 20 of 3,252
  cases, 60 rows newly deleted and none newly kept
  ([readings](../../readings/forget-keep-except.md)). Left open:
  [task 1204](1204-a-word-for-all-in-a-clause-holding-a-keep-verb-keeps-a-last-group-of-another-kind.md)
  and [task 1206](1206-a-german-article-in-a-keep-clause-keeps-every-row-holding-it.md).
