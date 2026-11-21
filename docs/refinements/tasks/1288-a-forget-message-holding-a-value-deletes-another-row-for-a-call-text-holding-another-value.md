# A forget message holding a value deletes another row for a call text holding another value

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-21

Over a locker code, a card and a phone that all end in `4242`, a message holding a value still
deletes a row it does not ask for when the call text holds another value, in unit calls through
`ForgetChosenTool`:

- `Forget my locker code 4242.` with the call text `my card is 4111` deletes the card.
- `Forget my gym code 9999.` with the same call text deletes the card too.

Both messages keep the phone for the call text `phone`. `_same_fact` and `_coded`
(`forget_permit.py`) read a call text holding a digit only in a message holding none, since a
message holding a value names rows by it: `Forget my bike code, it is 5521.` with the call text
`5521` deletes every row holding `5521` (`test_forget_unnamed.py`), and `Forget my locker code
and 0721 555 4242.` with that number as the call text deletes the phone. `permitted` returns
nothing for a call text holding a digit.

The card shows each row before anything is deleted.

## What to do

1. Write the near misses as tests first: the two messages above from `test_forget_unnamed.py`
   and `test_forget_call_narrows.py` still delete what they delete today, and `Forget 4242.`
   with the call text `4242` still deletes the locker code.
2. Replay `permitted` for a call text holding a digit when no value of the call text is a value
   of the message, so the rows each value of the message lists are the rows the call may list.
   Add no word to a word list.
3. Replay the generator and every string of the brain's forget tests: no row newly listed, and
   the count of rows newly kept that the message asks to delete.

## History

- 2026-11-21: filed while reading a call text holding a digit beside a code word
  ([R-1286](1286-a-forget-naming-a-code-deletes-another-row-after-a-word-for-all-or-for-a-code-word-in-another-number.md)).
