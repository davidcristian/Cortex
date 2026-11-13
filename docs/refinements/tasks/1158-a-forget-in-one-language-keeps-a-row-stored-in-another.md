# A forget in one language keeps a row stored in another

**Status:** done 2026-11-13
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

A plain forget naming a row only in words of another language than the row's deletes nothing
([readings](../../readings/forget-keep-plain-replay.md#readings)). Over the row `User: Remember
that my phone number is 0721 555 019.`, the message `Vergiss meine Telefonnummer 0721 555 019.`
with call text `0721 555 019` returns `KEPT_ALL`: `_split` reads the compound `Telefonnummer` as
naming `telefon`, so `named` holds, `every` needs `quantifies`, and `unnamed` keeps the row since
no word of the message is the row's. The same holds for `Oublie ma carte.` over an English card
row with call text `4111 1111 1111 4242` in a new chat. Over the English card ending in 4242
beside the English gym code `4242`, `Oublie la carte qui finit par 4242.` and `Vergiss die Karte,
die auf 4242 endet.` with call text `4242` keep both rows, since the message names no word of
either. 126 of 316 replayed cases with a message and row in different languages list nothing.

## What to do

1. Write the cases above as tests, with near misses that must still keep a row: a message in
   another language naming a different fact beside the same value.
2. Let a kind word name the same kind in each note language (`carte`, `Karte` and `card`;
   `Telefon` and `phone`) when `unnamed` and the last group keep compare the message with a row,
   then replay the strings of the readings through the old and new code.

## History

- 2026-11-12: filed from the replay of plain forgets through the destructive card.
- 2026-11-13: done. A closed table of card and phone words in the five note languages
  (`forget_kinds.py`) names a row of the same kind where `unnamed` and the last group keep
  compare the message's words with a row's, but lists no row in a message holding a negation or a
  word for minus. The replay changed only cases listing a row the message names
  ([readings](../../readings/forget-kind-and-value-names.md)). A card message still lists a phone
  row ending in the same group: task
  [1173](1173-a-forget-naming-a-card-lists-a-phone-ending-in-the-same-group.md).
