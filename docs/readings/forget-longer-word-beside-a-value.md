# Readings: a longer forget word beside a value

How the forget card reads a forget word one or two letters longer than a word of a row's request
(`extends` in `forget_kinds.py`) when the message also holds a value another row holds, as in
`Forget my cart 1234.` with the call text `car` beside a car row. The decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s; `permitted` (`forget_permit.py`)
implements it: beside such a value it adds only a row a word of the part asking to forget names by
a word the row holds or a kind word, never a row only `extends` reads.

## The replay, 2026-11-23

Unit calls through `ForgetChosenTool`, each case over its own rows with the call text it names.
The cases are 57 word pairs in the five note languages, each a message word one or two letters
longer than a row word: 20 are the row word in another number (`cars` of `car`, `Spinde` of
`Spind`), 37 are no form of it (`cart` of `car`, `plane` of `plan`, `song` of `son`).

- 4,104 cases with one other row holding the message's value: the row the word extends and a
  third row hold `4242`, a phone or locker holds `1234`, and the message is `Forget my cart 1234.`
  or one of 11 forms like it, with the call texts `4242`, `1234`, the message word and the row
  word.
- 12,768 cases with every row holding the message's value `4242`, in 16 opening forms and 13 keep
  clauses.
- The 57,916 cases of the forget card generator: 42,356 generated messages, 5,175 extra forms and
  10,385 calls over the strings of the brain's forget tests.

The counts compare each tree with the tree before `extends`.

| cases | tree | rows asked to keep listed | rows not asked for newly listed | rows asked to delete newly listed |
| --- | --- | --- | --- | --- |
| 4,104 | `extends` read by `permitted` | 12 | 135 | 65 |
| 4,104 | `permitted` reads no longer word | 12 | 0 | 0 |
| 12,768 | both | 902 | 0 | 0 |
| 57,916 | both | 0 | no change between the two | no change between the two |

Every one of the 135 and 64 of the 65 have the call text equal to the row word, as `car`. The 65
are the row word in another number (`Forget my cars 1234.`), which `extends` is for: not reading
it beside a value keeps all 65, which is the cost. A reading that keeps the 135 and lists the 65
needs a list of word endings by language, which the decision does not add. Every tree, the one
before `extends` too, lists the 12 and the 902 rows asked to keep. The 12 are in the 72 cases
whose rows repeat an id, so that no row holds `1234`.

The cases are written by `mk2.py` (4,104) and `mk.py` (12,768) and counted by `count.py`, in
`~/.cache/cortex-run/2026-11-23/f4/`, which also holds the generator in `f3gen/`;
`replay.sh after` takes the listings again, and the earlier trees' listings are in
`~/.cache/cortex-run/2026-11-23/a1/`.
