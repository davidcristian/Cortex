# A forget naming a code deletes another row for a call text holding a digit or after a word for all

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-21

Over a locker code, a card and a phone that all end in `4242`, two forms of a message naming a
code still delete a row the message does not ask for, in unit calls through `ForgetChosenTool`:

- `Forget my gym code.` with the call text `my card is 4111` deletes the card, and with `phone is
  0721` the phone. `_coded` (`forget_permit.py`) reads a call text holding no digit only, and
  `_same_fact` needs a word of the message naming a stored row, which `gym` does not.
- `Forget every code.` and `Forget all my codes.` with the call text `phone` delete the phone.
  `_coded` reads no message holding a word for all, since `Forget everything and my code.` with
  that call text asks for the phone too, and no stored request holds `codes`.

The card shows each row before anything is deleted. A code word that no stored request holds
permits what the call names, as any message naming no stored row does: `Forget my gym
password.` with the call text `phone` deletes the phone.

## What to do

1. Write the near misses as tests first: `Forget that code.` with the value of a card the chat
   just stored as the call text still deletes the card, and `Forget everything and my code.` with
   the call text `phone` still deletes the phone.
2. For the first form, replay the rule of `_coded` for a call text holding a digit, with the row
   `just_said` reads still permitted.
3. For the second, read a word for all right before the code word as a limit, as the limit
   readers do for `all my card numbers`. Add no word to a word list.
4. Replay the generator and every string of the brain's forget tests: no row newly listed, and
   the count of rows newly kept that the message asks to delete.

## History

- 2026-11-21: filed from the close of
  [R-1225](1225-a-forget-call-naming-a-row-beside-a-code-word-or-in-a-text-holding-a-digit-still-deletes-it.md),
  which reads the two forms it names and leaves these.
