# A word naming another row in a clause about the value lists it on the forget card

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

The forget card (`kept_rows` in `forget_inside.py`, `unnamed` in `forget_unnamed.py`) lists a row
that a word of the message names, a shared word or a kind word of `forget_kinds.py`, wherever the
word stands. A message that names another row only to say where the value was written or sent
lists that row too. With the rows `Remember that my locker code is 4242.` and
`Remember that my phone is 0721 555 4242.`, the call text `4242` and the message
`Forget the locker code 4242 that I texted from my phone.`, the card lists and deletes both rows.
The same happens with `Oublie le code 4242 du casier, il est noté sur la carte du parc.` beside an
English card row ending in `4242` (the kind word `carte`), and with
`Forget my gym code 4242, the one written on the birthday card.` beside `my card is 4111 1111 1111
4242`. With `plan` or `laptop` in place of the kind word, the card keeps the second row. The start
build `cec7c748f` and HEAD `c0e02329e` both list it. The person still sees the card before the
delete, so nothing is lost unseen. The probe is `probe.py` with `cases2.json` and `cases3.json` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot10/`.

## What to do

1. Write tests first: each message above keeps the second row and lists the first; a message
   naming both rows as the ones to forget (`Forget my phone and card numbers ending 4242.`) still
   lists both.
2. Keep a row that holds the call's text only as a group of a longer value when the message names
   another row holding that text whole and names the first row by a word only in a clause that is
   not the one asking to forget, by the clause's shape rather than a list of words; the kept note
   names it, which is the safe direction.
3. Replay every recorded message and test string through the card, then draw the neighbouring
   flows (forget what was just said, a value named alone, another chat's row).

## History

- 2026-11-13: filed by the first audit of the night, which reproduced it on both builds.
