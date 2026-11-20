# A word no stored row holds after a word for all lists every row holding the value

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-20

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, `Forget all cupboards 4242.` and `Forget
the bike 4242 everywhere.` with the call text `4242` delete all three, and with the call text
`phone` they delete the phone. `limited` (`forget_kinds.py`) stops a word for all only at a kind
word or a word that a word of a matched row starts, and `cupboards` and `bike` are neither. The
word is where a row's name is, so it may name a row the store does not hold, and then the
message asks for none of the three. This is the unsafe direction: the card lists rows the
message does not name. `test_forget_every_kind.py` asserts the reading for `Forget all lockers
4242.` over a card and a phone.

`Forget every other 4242.` and `Forget every single 4242.` ask for every row, and their tests
hold that. No reader tells `other` from `cupboards`: neither names a stored row, and no table of
`forget_forms.py` holds a word that only modifies a word for all.

## What to do

1. Write the near misses first: `every other 4242`, `every single 4242`, `all the 4242`, `all
   these 4242` and `all of 4242` must list every row holding the value, as today.
2. Propose a row of the table of forms for the words that only modify a word for all, with its
   cell for each language or the reason a cell is empty, and read every other word between a
   word for all and the value, of three letters or more and no function word, as a row name no
   stored row holds, which keeps every row. The words of that row are a pick for the user.
3. Replay the generated messages with each word of the row and with words no pool row holds, in
   both places: after a word for all, and before a value a word for all follows. Rows newly
   listed must be zero.

## History

- 2026-11-20: filed from the close of
  [R-1234](1234-a-word-for-all-before-a-row-word-in-a-form-no-stored-row-holds-lists-every-row.md),
  which reads a longer form of a stored row word and leaves a word no stored row word starts.
