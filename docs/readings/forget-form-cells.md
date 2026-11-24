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
