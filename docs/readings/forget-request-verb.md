# Readings: a form of the request's own verb in a forget message

How the forget card (`ForgetChosenTool`) reads a message quoting a form of the verb every stored
request opens with, such as `Forget what you remembered about my card.`, since `_apart`
(`forget_keep_named.py`) drops each word every request of two or more rows read holds before
`extends` and `grows` (`forget_kinds.py`) read a row in `forget_named`. `remembered` is
`remember` with two letters added, so before the change it named every English row and the call
text `4242` deleted the phone beside the card. The decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s.

## The replay, 2026-11-26

Method: every case set through the card at the tree before and after the change, in unit calls
over the in-memory store, counted per row against what the message asks (`D` delete, `K` keep,
`N` not asked for). Two sets are new. The request verb family quotes a form of the request's verb
(`remembered`, `remembers`, `remembering`, `rememberance`, `retenu`, `retiens`, `gemerkt`,
`merken`, `recordaste`, `recuerdas`, `ținut minte`, `mintea` and more) beside a row word, over the
three rows of each of the five languages, for the call text `4242` and each row word in two row
orders. The second set has the verb form alone, or beside the Romanian plural `cardurile` or
`dulapurile`. The scripts are in `~/.cache/cortex-run/2026-11-26/x0/` (`rvgen.py`, `rv2gen.py`,
`replay.sh`, `cmp.py`).

| Case set | Cases | Asked to keep, listed | Not asked for, listed | Asked to delete, kept |
| --- | --- | --- | --- | --- |
| Request verb family | 2,184 | 0 and 0 | 176 then 0 | 1,652 and 1,652 |
| Verb alone or beside a plural | 464 | 0 and 0 | 286 then 262 | 46 and 46 |
| Plural set | 640 | 0 and 0 | 64 and 64 | 570 and 570 |
| Generator | 71,332 | 0 and 0 | 861 and 861 | 33,505 and 33,505 |
| Word pairs | 12,768 | 0 and 0 | 415 and 415 | 2,189 and 2,189 |
| Negated messages | 8,376 | 0 and 0 | 0 and 0 | 5,448 and 5,448 |
| Mixed builder | 13,827 | 0 and 0 | 0 and 0 | 8,882 and 8,882 |
| Valued messages | 4,104 | 0 and 0 | 3 then 0 | 4,517 and 4,517 |

No row is newly listed in any set and no row asked to delete is newly kept, so the change costs
nothing over these sets. Besides the counted rows, the generator's messages that quote a tool
result (`forgot 1 remembered exchanges`) ask for no row, and 10 rows they listed by the call text
are no longer listed. In the family the 176 rows follow `remembered`, `remembers`, `rememberd`
and `rememberer` (28 each), `mintea` and `mintele` (12 each), `recuerdas`, `recuerdan`,
`recuerdame`, `retiense` and `retiensr` (8 each). The 24 of the second set follow `mintea`,
`mintele` and `minteaua` beside `cardurile` and `dulapurile` (4 each), where `minteaua` is
three letters longer than `minte` and so named every row by `grows`. The 3 valued rows follow
`Forget my remembered 1234.` and two forms of it.

With one row read, its words still name it: without that condition two rows asked to delete in
the valued set are kept, as for `Forget my lockers 1234.` with the call text `locker`.

The 1,652 rows asked to delete that the family keeps are kept at both trees: most forms of the
family delete nothing, a cost that
[the freeze record](forget-freeze.md#forms-left-unread-at-the-freeze-2026-11-26)
keeps.
