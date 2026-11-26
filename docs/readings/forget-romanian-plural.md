# Readings: a Romanian plural row word in a forget message

How the forget card (`ForgetChosenTool`) reads a Romanian plural of a row word, such as
`cardurile` for a row holding `cardul`, since `grows` (`forget_kinds.py`) reads a word of a
forget verb's clause that is three or more letters longer than a word or code word of a row's
request and starts with it, or with it less its last letter, four letters at least, when no
other word of the message names a row. The decision
is [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s.

## The replay, 2026-11-26

Method: every case set through the card at the tree before and after the change, in unit calls
over the in-memory store, counted per row against what the message asks (`D` delete, `K` keep,
`N` not asked for). The plural set is new: each of `codurile`, `cardurile`, `dulapurile`,
`telefoanele`, `coduri`, `carduri`, `dulapuri` and `telefoane`, alone or after `toate`, with or
without `4242`, over the rows `Ține minte că codul de la dulap este 4242.`, `Ține minte că
cardul meu este 4111 1111 1111 4242.` and `Ține minte că telefonul meu este 0721 555 4242.`,
for ten call texts in two row orders. The scripts are in `~/.cache/cortex-run/2026-11-26/f4/`
(`plgen.py`, `replay.sh`, `cmp.py`).

| Case set | Cases | Asked to keep, listed | Not asked for, listed | Asked to delete, kept |
| --- | --- | --- | --- | --- |
| Plural set | 640 | 0 and 0 | 128 then 64 | 570 and 570 |
| Generator | 71,332 | 0 and 0 | 881 then 861 | 33,505 and 33,505 |
| Word pairs | 12,768 | 0 and 0 | 417 then 415 | 2,189 and 2,189 |
| Negated messages | 8,376 | 0 and 0 | 0 and 0 | 5,448 and 5,448 |
| Mixed builder | 13,827 | 0 and 0 | 0 and 0 | 8,882 and 8,882 |
| Valued messages | 4,104 | 0 and 0 | 3 and 3 | 4,517 and 4,517 |

No row is newly listed in any set, and no row asked to delete is newly deleted. Of the plural
set's 64 rows not asked for still listed, 16 each follow `telefoanele` and `telefoane`, whose
stem changes (`telefoan` of `telefon`), and `carduri` and `coduri`, one letter longer than
`cardul` and `codul`: the call text decides for them, as for any message naming no row. With
the call text `4242`, which every row holds, `Uită cardurile.` keeps every row where `Uită
cardul.` deletes the card: the reader of the rows a message leaves unnamed (`unnamed` in
`forget_unnamed.py`) does not read `grows`, so the misread keeps the row.
