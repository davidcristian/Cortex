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

## A message lacking the value, 2026-11-24

The 902 rows and 9 of the 12 above are a later clause naming a row, with no keep verb, in a
message that does not hold the call's value: `Forget my cart, the phone stays.`,
`Oublie mon cart, le casier reste.`, `Olvida mi cart, el gimnasio se queda.`, `Uită cart, dulap
rămâne.`, and `Forget my lockers 1234, the phone stays.` with the text `4242`. The readers of
the words after the value (`after_value`, `beside`, `kept_again`) start only at the value, so
they read nothing in such a message. The rule: a message holding no place of the call's value
reads the end of each clause holding a forget verb as that place (`forget_end` in
`forget_clauses.py`), for the words after it and for the words before it (`before_value`), so
the words of the forget clause still name the rows the message asks to delete.

| cases | rows asked to keep that the card lists, before | after | rows asked to delete newly kept | rows newly listed |
| --- | --- | --- | --- | --- |
| 12,768 word pair cases | 902 | 0 | 0 | 0 |
| 4,104 longer word cases | 12 | 3 | 0 | 0 |
| 71,332 generated and literal cases | 0 | 0 | 0 | 0 |

The same rule without the words before the value keeps 40 more rows the message asks to delete,
as the phone of `Forget my phones, the locker stays.`. The 3 left have the call text equal to
the row word that the later clause holds, as `Forget my phones 1234, the phone stays.` with the
text `phone`: the message holds that text, so the value's place is in the keep clause
([R-1334](../refinements/tasks/1334-a-call-text-that-is-the-row-word-a-later-clause-keeps-lists-that-row.md)).
The cases are counted by `ucount.py` and `count.py` in `~/.cache/cortex-run/2026-11-24/f5/`;
`replay.sh head` and `replay.sh new` take the listings at the two trees.

The rule also reads a message holding `4242` in a form the reader does not take as the value:
`42 42`, `42-42`, `4 2 4 2`, `4.242`, two number word forms in each of the five languages, or
split by the later clause, as `Forget the card 42, keep the phone, 42.`. Over 6,588 such
messages it lists none of the 4,116 rows asked to keep, where the tree before it listed 492,
newly lists no row, and keeps 632 more rows asked to delete, as the phone and the locker of
`Forget all 42 42, the card stays.`. The cases are written by `mkforms.py` and counted by
`bform.py` in `~/.cache/cortex-run/2026-11-24/a3/`.

## A call text only in a later clause, 2026-11-25

The 3 rows left above have a call text that is a word naming a row, which the message holds only
after its first clause holding a forget verb. The readers of the words after the value now read
such a text as `kept_again` reads a later place of it: as the row's name, with the end of the
forget clause as the value's place (`_held` in `forget_clauses.py`). The words before the value
(`before_value`) are still read up to the text's place.

| cases | rows asked to keep that the card lists, before | after | rows asked to delete newly kept | rows newly listed |
| --- | --- | --- | --- | --- |
| 4,104 longer word cases | 3 | 0 | 0 | 0 |
| 12,768 word pair cases | 0 | 0 | 0 | 0 |
| 71,332 generated and literal cases | 0 | 0 | 42 | 0 |
| 3,864 forget of everything cases | 340 | 312 | 0 | 0 |
| 6,156 mixed messages | 0 | 0 | 0 | 0 |
| 8,376 negation cases | 0 | 0 | 0 | 0 |

The cost is the 42 rows, in 21 literal calls over the strings of the brain's forget tests, two in
each: the row the call text names and the row holding it inside a longer word (`téléphone` of
`phone`, `cardul` of `card`). An example is the phone of `Forget the card 4242, the phone and the
locker too.` with the text `phone`: the call matches no locker row, so `locker` is a word no
reader reads and the later clause names the phone under a role no reader reads. 20 of the 21
messages ask to delete that row, and the last is a result text. No generated message asks to
delete a row the reading now keeps. It also keeps 12 rows the generator marks as either outcome,
in the mixed messages, and 28 rows asked to keep in Spanish and Romanian forgets of everything,
as `Olvida todo, la tarjeta se queda.`. The listings are taken by `replay.sh base` and `replay.sh
a1334` and compared by `cmp.py` in `~/.cache/cortex-run/2026-11-25/f1/`.
