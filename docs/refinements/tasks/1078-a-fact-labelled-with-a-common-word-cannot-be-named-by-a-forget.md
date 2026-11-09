# A fact labelled with a common word cannot be named by a forget

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`_words` in `forget_unnamed.py` drops every word of `_COMMON`, which holds `user`, `one` and
`memory` because each row starts with `User:`. With a `my user id is 7319` row and a shed padlock
row holding 7319, `Forget my user id 7319.` leaves no word, so `unnamed` keeps nothing and the card
lists both rows; `Forget the one that is 7319.` does the same
([readings](../../readings/forget-shared-number.md#audit-probes-of-the-keep-reader-2026-11-09)).

## What to do

1. Read a row's words after its `User:` and `Assistant:` prefixes are removed, so `user` and
   `assistant` can name a fact, and keep `_COMMON` for words that name none.
2. Test `Forget my user id 7319.` against both rows, and replay the recorded forget draws.

## History

- 2026-11-09: filed from the audit probes of the keep reader.
