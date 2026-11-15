# A forget call naming a row beside a value, a code word or a mixed text still deletes it

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

On 2026-11-15 the forget card began keeping a match of a call text holding no digit that no word
of the message names, when the message holds no digit and a word of its part asking to forget
names another stored row (`forget_named` in `forget_keep_named.py`). Three forms of the same call
still delete a row the message does not ask for, in unit calls through `ForgetChosenTool` over a
locker code, a card and a phone that all end in `4242`:

- `Forget my gym code.` with the call text `phone` deletes the phone. No word of the message names
  a stored row: `gym` is in none, and `code` is a code word, which names no fact.
- `Forget the 4242 of my locker.` with the call text `phone` deletes the phone. The message holds
  a digit, and `Forget 4242, the card too.` with the same call must delete the phone.
- `Forget my locker code.` with the call text `my card is 4111` deletes the card. The text holds a
  digit, so `_unnamed_groups` keeps it only when the row holds the text inside a longer value.

The card shows each row before anything is deleted.

## What to do

1. Write the near misses as tests first: `Forget 4242, the card too.` and `Forget what I just told
   you.` with the call text `phone` must still list the phone, and a recalled exchange holding the
   value only in its reply must still be deleted beside the fact (`test_forget_unnamed.py`).
2. For the first form, read a code word of the message as naming the stored rows whose request
   holds a code word, in `forget_named` and in the `named` rows of `_unnamed_groups` alike, so
   `Forget my code.` with the call text `gym code` still deletes a lone gym code.
3. For the second, read the limit after the value (`beside` in `forget_clauses.py`) for a call text
   holding no digit as it is read for one holding the value.
4. Replay the three pools of the reading: no row newly listed, and each newly kept row one the
   message does not ask for.

## History

- 2026-11-15: filed from the calls the store read of the message's named rows does not reach
  ([readings](../../readings/forget-everything-but-call.md#a-call-naming-a-row-the-message-does-not-name-2026-11-15)).
