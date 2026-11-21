# A forget naming a code deletes another row after a word for all or for a code word in another number

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-21

Over a locker code, a card and a phone that all end in `4242`, two forms of a message naming a
code still delete a row the message does not ask for, in unit calls through `ForgetChosenTool`:

- `Forget every code.` with the call text `phone` deletes the phone, and with `my card is 4111`
  the card. `_coded` (`forget_permit.py`) reads no message holding a word for all, since `Forget
  everything and my code.` with either call text asks for that row too.
- `Forget my codes.` and `Forget all my codes.` with the same call texts delete the same rows.
  `_coded` compares each code word of the message with the words of a stored request, and the
  stored request holds `code`, not `codes`. This form needs no word for all.

A word naming a row reads the same way as the second form: `Forget my cards.` with the call text
`phone` deletes the phone, since `cards` names no stored row for `forget_named`, while `Forget
every card.` keeps it.

The card shows each row before anything is deleted. A code word that no stored request holds
permits what the call names, as any message naming no stored row does: `Forget my gym
password.` with the call text `phone` deletes the phone.

The two forms need two readers. A reader of a word for all before a code word leaves `Forget all
my codes.` as it is. A reader that takes `codes` for `code` has to say which longer form is the
same word in each of the five languages (`codul`, `códigos`, `Codes`, `numéros`), and the
readers have that for no row word either, so written for code words alone it leaves `Forget my
cards.` as the next form.

## What to do

1. Write the near misses as tests first: `Forget everything and my code.` with the call text
   `phone` still deletes the phone, `Forget every code 4242.` with the call text `4242` still
   deletes the locker code, and `Forget my gym password.` with the call text `phone` still
   deletes the phone.
2. Write one comparison of a message word with a request word in another number, used by both
   `_coded` and `forget_named`, so `codes` and `cards` are read by one rule. Add no word to a
   word list.
3. Then read a word for all right before the code word as a limit, as the limit readers do for
   `all my card numbers`.
4. Replay the generator and every string of the brain's forget tests: no row newly listed, and
   the count of rows newly kept that the message asks to delete.

## History

- 2026-11-21: filed from the close of
  [R-1225](1225-a-forget-call-naming-a-row-beside-a-code-word-or-in-a-text-holding-a-digit-still-deletes-it.md),
  which leaves these forms. A message holding a value beside a call text holding another is
  filed apart:
  [R-1288](1288-a-forget-message-holding-a-value-deletes-another-row-for-a-call-text-holding-another-value.md).
