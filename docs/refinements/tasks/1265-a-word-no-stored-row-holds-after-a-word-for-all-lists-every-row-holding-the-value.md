# A word no stored row holds after a word for all lists every row holding the value

**Status:** done 2026-11-25
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

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
   cell for each language or the reason a cell is empty. The generator needs `other` and
   `single` in the English cell. The words of that row are a pick for the user.
3. Then read every word between a word for all and the value that `row_words` keeps, less the
   function words and that row, as a row name: in `quantifies` (`forget_unnamed.py`), take
   `named` from the query's own words as well as the rows'. Without the row this rule keeps 498
   rows the generated messages ask to delete, all under `other` or `single`.
4. Replay the generated messages with each word of the row and with words no pool row holds, in
   both places: after a word for all, and before a value a word for all follows. Rows newly
   listed must be zero.

## History

- 2026-11-20: filed from the close of
  [R-1234](1234-a-word-for-all-before-a-row-word-in-a-form-no-stored-row-holds-lists-every-row.md),
  which reads a longer form of a stored row word and leaves a word no stored row word starts.
- 2026-11-23: still open. Reading the query's own words as row names in `quantifies` keeps all
  264 rows that the 180 generated calls of this form do not ask for and lists no row newly, over
  the generator in `~/.cache/cortex-run/2026-11-23/f2/`. It also keeps 498 rows that
  `every other 4242` and `every single 4242` ask to delete in five languages, and 13 forget
  tests change, so it waits for the table row of step 2.
- 2026-11-24: still open. At the tree that reads a later clause in a message lacking the value,
  the 180 generated calls of this form still list the 264 rows they do not ask for, over the
  71,332 cases of the generator in `~/.cache/cortex-run/2026-11-24/f5/` (`f3gen/`, counted by
  `ncount.py`). Reading the query's own words as row names in `quantifies` keeps all 264, lists
  no row newly, and keeps 498 rows asked to delete, 249 under `other` and 249 under `single`.
  The table row of step 2 is a new list of words, which waits for the user's pick of its words.
- 2026-11-25: done. `quantifies` takes `named` from the message's own words as well as the
  rows', less the function words, without the table row of step 2. Over the 71,332 generated
  and literal cases it keeps the 264 rows, lists no row newly, and keeps 498 rows asked to
  delete under `other` and `single`; no other case set changes
  ([readings](../../readings/forget-everything-unread-role.md#a-word-of-the-message-no-stored-row-holds-2026-11-25)).
  The table row is filed as
  [R-1338](1338-words-that-only-modify-a-word-for-all-are-read-as-a-row-name.md), whose words
  are the user's pick.
