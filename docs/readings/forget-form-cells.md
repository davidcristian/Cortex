# Readings: each empty cell of the forget card's table of forms, filled alone

How the forget card (`ForgetChosenTool`) reads a message once one empty cell of the table of forms
(`FORMS` in `forget_forms.py`) holds its word, and nothing else changes. The decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s; the replay of every translation at once
is in [forget-everything-but-call.md](forget-everything-but-call.md#the-words-read-for-a-form-by-language-2026-11-15).

## The cells replayed one at a time, 2026-11-24

Each cell was filled alone in a copy of HEAD `a84198033`'s core and replayed over the messages of
its language that the forget card generator writes, over the stored rows each message names and
with its value as the call text: 11,984 French, 10,842 German, 10,791 Spanish and 9,555 Romanian messages. Each
message's oracle marks every row as asked to delete, asked to keep, not asked for, or unsure (a
row a later clause takes back). A count is of rows whose card result changed against HEAD.

| Cell | Asked to delete, now deleted | Asked to keep, now listed | Not asked for, now listed | Unsure, now listed |
| --- | --- | --- | --- | --- |
| all, ro: `toate` | 441 | 10 | 36 | 0 |
| only, fr: `seulement` | 972 | 0 | 76 | 262 |
| only, de: `nur` | 580 | 0 | 102 | 62 |
| only, es: `solo` | 858 | 0 | 114 | 208 |
| only, ro: `doar` | 535 | 0 | 53 | 140 |
| also, es: `también` | 1,076 | 0 | 36 | 108 |
| also and only, es: `también` and `solo` | 2,098 | 0 | 170 | 338 |
| also and the or my, es: `también` and `el los mi mis` | 1,256 | 0 | 40 | 112 |

No cell keeps a row asked to delete that HEAD deletes. Where the rows come from:

- `toate`: all 10 rows asked to keep are named in the plural in a keep clause, as in
  `Uită toate 4242, cardurile rămâne.`; the 36 not asked for are in messages that also hold `doar`,
  `și` or `tot`, as in `Uită toate 4242 exceptând cardul doar de pe card.`.
- A word for only: all 76 rows not asked for of `seulement` and all 53 of `doar` are in messages
  where another clause adds, keeps or excepts a row. So are 90 of the 102 of `nur`, and the other
  12 follow `nicht` (`Vergiss 4242, nicht die Karte, nur die Karte.`). Of the 114 of `solo`, 94
  are, and 20 name a row by a word another stored row shares (`Olvida 4242, solo la tarjeta.`
  with a new card stored), as HEAD already lists in `Olvida la tarjeta 4242.`.
- `también`: 28 of the 36 rows not asked for are beside `solo`, as in
  `Olvida 4242, el teléfono también, solo la tarjeta.`; the other 8 are a row named by a word
  another row shares (`la tarjeta` with a new card stored), which HEAD already lists in
  `Olvida la tarjeta 4242.`. With `el los mi mis`, all 4 more rows not asked for are beside `solo`.
- English `only` lists the same kind of row on HEAD: `Forget all 4242, the card too, only the
  phone.` deletes the card and the locker code.
- Filled, `doar` deletes the card on the Polish `Zapomnij 4242, doar card.`, which HEAD leaves.

`de asemenea` is two words and a cell holds one word per entry, so it was not replayed. Scripts
`variants.py`, `cells.sh`, `toate.sh`, `cells_diff.py` and `detail.py`, logs `cells_diff.txt`
and `ro_diff.txt`, in `~/.cache/cortex-run/2026-11-24/f3/`.

## A word for only read as a limit beside another clause, 2026-11-26

The forget card keeps each row that a run after the value holding a word for only, read as a
limit, does not name (`alone` in `forget_only.py`), whatever other clause the message holds. The
replay is over the generator's 71,332 messages, the 3,864 forgets of every value, the 6,156 and
13,827 mixed messages, the 12,768 word pairs, the 4,104 valued messages and the 8,376 negated
messages, against HEAD `f71fb6d13`.

| Tree | Asked to keep, listed | Not asked for, listed | Asked to delete, kept |
| --- | --- | --- | --- |
| HEAD | 0 | 1,254 | 33,355 |
| `alone` | 0 | 881 | 33,505 |
| `alone`, then `seulement` filled | 0 | 885 | 32,625 |
| `alone`, then `nur` filled | 0 | 851 | 32,997 |

All counts are over the generator; every other set is unchanged in every row. `alone` lists no
row HEAD keeps. It keeps 373 rows not asked for that HEAD lists, as the card of `Forget 4242, the
card too, only the phone.`, and 150 rows asked to delete, each added by a clause after the run
(`Forget 4242, only the card, the phone too.`). Read only beside a clause adding, keeping or
excepting a row, it kept 113 fewer rows not asked for and the same 150 rows asked to delete.

After `alone`, `seulement` deletes 880 rows asked to delete and `nur` 508, and they newly list 56
and 22 rows not asked for, all in a run that adds a row, by an adding word or a first word for
and, and holds the word for only: `Oublie 4242, aussi la carte seulement sur le téléphone.`,
`Vergiss 4242 und das Handy nur auf der Karte.`. English lists 64 rows in the same form, as in
`Forget 4242, also the card only on the phone.` and `Forget 4242 and the card only on the
phone.`. Scripts `replay.sh`, `both.sh`, `three.sh`, `cmp.py` and `forms.py` in
`~/.cache/cortex-run/2026-11-26/f2/`.

## A word for only beside a call naming a row, 2026-11-26

A call text holding the value beside a word of a row, as `locker 4242`, `code is 4242` or the row's
whole request, matches that row alone, so `alone` in `may_keep` read `phone` of `Forget 4242, the
card too, only the phone.` as a word naming no row and kept nothing. `_kept_later` in
`forget_permit.py` now reads the same runs, after the message's value that the call's text holds,
with every word of the message naming a stored row, and keeps each row of the card that the run
leaves out. The word for only generator writes 3,420 such messages in five languages, 12 forms, each
with the value as the call text and three call texts per row (`onlygen.py`).

| Set | Messages | Asked to keep, listed | Not asked for, newly listed | Asked to delete, newly kept |
| --- | --- | --- | --- | --- |
| word for only generator, before | 3,420 | 444 | | |
| word for only generator, after | 3,420 | 324 | 0 | 0 |
| every other set, after | 140,200 | unchanged | 0 | 3 |

The other sets are the generator's 71,332 messages, the forgets of every value, both mixed sets,
both word pair sets, the valued and negated messages, and every set of the a1 and x1 slots. The
120 rows no longer listed are all English. The 3 rows newly kept are the phone rows of `Forget
everything, only the card.`, which the reading "only the card" keeps. The 324 left are 300 in the
four languages whose cell for only is empty and 24 English rows in `Forget 4242 and only the
phone.` and `Forget only the phone 4242.`
([task 1365](../refinements/tasks/1365-a-word-for-only-the-card-leaves-unread-lists-a-row-asked-to-keep.md)).
Scripts `onlygen.py`, `replay.sh`, `both.sh` and `cmp.py` in `~/.cache/cortex-run/2026-11-26/f5/`.
