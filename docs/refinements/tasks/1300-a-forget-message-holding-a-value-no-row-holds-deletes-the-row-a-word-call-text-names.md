# A forget message holding a value no row holds deletes the row a word call text names

**Status:** done 2026-11-23
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

Over a locker code, a card and a phone, in unit calls through `ForgetChosenTool` on 2026-11-22:

- `Forget 9999.` with the call text `phone` deletes the phone, and with `card` the card.
- `Forget my gym password 9999.` with the call text `phone` deletes the phone.

No stored row holds `9999`, so `permitted` (`forget_permit.py`) returns nothing. The message names
no stored row and no code word, so `_same_fact` and `_coded` return nothing too, and the call
lists what its text names. The same two messages keep the card for the call text
`my card is 4111`, which `_apart` reads, and `Forget my gym code 9999.` keeps the phone for the
call text `phone`, which `_coded` reads.

`test_forget_call_narrows.py` asserts the same delete for a message holding no value:
`Forget my gym password.` with the call text `phone` deletes the phone, because a message that
names nothing stored leaves the choice to the call text. A message holding a value names rows by
that value, so the question is whether a value no stored row holds permits a call to list nothing.

The card shows each row before anything is deleted.

## What to do

1. Write the two messages as tests first, and beside them the calls that must still delete:
   `Forget that.` and `Forget my gym password.` with the call text `phone`, and
   `Forget my card, I got it on 12 March.` with the call text `card`.
2. Read a call text holding no digit as `_apart` reads one holding a digit, when the message holds
   a whole value and no stored row holds any value of the message. Add no word to a word list.
3. Replay the generator and every string of the brain's forget tests: no row newly listed, and
   the count of rows newly kept that the message asks to delete.

## History

- 2026-11-22: filed after a call text holding a digit beside a message holding another value
  was read
  ([R-1288](1288-a-forget-message-holding-a-value-deletes-another-row-for-a-call-text-holding-another-value.md)).
- 2026-11-23: done. A call text holding no digit beside a message holding a whole value that no
  stored row matches is read as `_apart` reads one holding a digit, and `_same_fact` reads the rows
  such a message names. Over the generator and 10,295 calls of the test strings no row was newly
  listed, the 51 rows listed for the 72 new messages are kept, no near-miss row is newly kept, and
  of the 96 rows newly kept under a string holding a forget verb none is one it asks to delete and
  4 are rows `Forget my bike lock code and all 7319s.` may ask for
  ([readings](../../readings/forget-everything-but-call.md#a-call-naming-a-row-the-message-does-not-name-2026-11-15)).
