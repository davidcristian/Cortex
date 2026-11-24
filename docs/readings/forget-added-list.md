# Readings: a clause adding a list of rows to a forget

How `asking` (`forget_remarks.py`) reads a clause after a forget that adds two or more rows, such
as `the phone and the locker too`. The form adding one row is in
[forget-remark-about-the-value.md](forget-remark-about-the-value.md). The decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s.

## A list joined by a word for and, 2026-11-15

Over `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111 4242.` and
`Remember that my phone is 0721 555 4242.`, with the call text `4242`. Before, `_adds` read an
adding clause only as one word for the or my and then fact words, so `Forget the card 4242, the
phone and the locker too.` and `Forget the card 4242, my phone and my locker too.` read the clause
as a remark and kept the phone row. `_adds` now splits the words between the adding word and the
other end of the clause at each `and`, `et` or `und`, and reads the clause as adding when every
item is a word for the or my, then only fact words of rows holding the text, then an optional
`one`. Both messages now delete all three rows. So do `Forget the locker code 4242, also my phone
and my card.`, `Oublie le code 4242 du casier, mon téléphone et la carte aussi.` and `Vergiss den
Code 4242 vom Spind, mein Handy und die Karte auch.`.

A clause stays a remark, which keeps the row, when an item has no word for the or my (`the phone
and card too`, `the phone and that card too`), names no row (`the phone and the passport too`), is
empty (`the phone and the card and too`) or is no such item (`the phone and I are done too`). A
word for or joins no list (`the phone or the card too`), since it asks for one of the rows. After a
clause ending in a keep clause the list is kept: `Forget the card 4242, keep the locker, my phone
and my gym too.` keeps the locker, the phone and the gym. `_ADD` has no Spanish or Romanian word,
so `mi teléfono y la tarjeta también` and `telefonul și cardul de asemenea` stay remarks. A first
item before a comma (`the phone, the locker and the gym too`) is read in the next section. The
tests are `test_forget_added_list.py`.

Replay: every string literal of the brain's forget tests and every backticked string of
[forget-remark-about-the-value.md](forget-remark-about-the-value.md), 1,553 strings, through the
card on the start commit and on the change. Each string runs over a pool of three rows (a locker
code, a card and a phone) and a pool of 18 rows (those, a gym code and a badge, with the locker
code, card and phone rows also in French, German, Spanish and Romanian). Every row holds each four
digit value of the string in turn, or `4242` when it has none, and the call text is that value:
3,252 cases. 17 cases from 11 strings changed, each a message with a list this change reads. 101
rows are newly deleted and none newly kept, and each newly deleted row is one an item of the list
names by its word or its kind. The scripts `replay.py` and `compare.py` and the listing `cmp1.txt`
are in the `slot2` scratch directory of the 2026-11-15 run.

## A first item before a comma, 2026-11-24

Over the same three rows and `Remember that my gym code is 4242.`, with the call text `4242`.
Before, `asking` read each clause between commas alone, so `Forget the card 4242, the phone, the
locker and the gym too.` read `the phone` as a remark and kept the phone row. `_listing`
(`forget_remarks.py`) now reads the clauses from the last one back, and reads a clause that is one
item as adding rows when the clause after it only adds rows, by `_adds` or by this same rule. That
message now deletes all four rows, and so do `Oublie le code 4242 du casier, mon téléphone, la
carte aussi.` and `Vergiss den Code 4242 vom Spind, mein Handy, die Karte auch.`.

An item stays a remark, which keeps its row, before a keep clause (`my phone, keep the locker and
the gym too`), before a clause that adds no row (`the phone, I think, the gym too`), at the end of
the message (`my phone too, my gym`), and before a list joined by a word for or. After a clause
ending in a keep clause the items are kept, as the list is above, and after a clause any reading
of a keep clause keeps, such as `but the phone` or `the phone stays`, the next item is kept too
([readings](forget-keep-any-reading.md#an-item-after-a-keep-clause-2026-11-24)).

Replay: the forget card generator of the 2026-11-23 run with this form added, 63,877 cases of
which 10,670 are the string literals of the brain's forget tests, and the 12,768 word pair cases
and 4,104 valued cases of the 2026-11-23 audit, through the card on the commit before the change
and on the change. No row the message asks to keep is listed on either. The rows the message asks
to delete that the card keeps fell from 30,918 to 30,889: 29 cases of the first item form each
deleted one more row it asks to delete, 13 English, 8 French and 8 German. No other case changed.
The scripts `replay.sh`, `cmpall.py` and `f3gen/count3.py` and the counts `c3_head.txt` and
`c3_x.txt` are in `~/.cache/cortex-run/2026-11-24/f1b/`.
