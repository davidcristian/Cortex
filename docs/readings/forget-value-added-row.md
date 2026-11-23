# Readings: a row added after a value alone

How the forget card reads a message asking for a value and then adding a stored row, as
`Forget 4242, the card too.`. The decision is [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s;
`adds_to_value` (`forget_value_added.py`) implements it and `unnamed` (`forget_unnamed.py`)
reads it.

## The rule

The message is a forget verb, optionally a word for the or my, the value, and then only words
that add rows: a word naming a stored row, a word for the or my, a word for and, and an adding
word (`too`, `also`, `aussi`, `auch`, `as well`) or a word for and as the first word after the
value. Such a message asks for every row holding the value whole, so the reader that keeps a row
no word of the message names keeps none. A row holding the value only inside a longer value is
still kept, as for `Forget 4242.`. Any other word before or after the value leaves the message to
the readers it had before, which keep rows.

## The replay, 2026-11-23

Unit calls through `ForgetChosenTool`, each case over its own rows with the call text it names:
the 57,916 and 57,096 calls of the two forget card generators (opening forms, then one or two
clauses over 3 rows in the 5 note languages, extra forms and the strings of the forget tests)
and 16,872 word pair cases. The listings are `f3_head.json`, `f3_after.json`, `f2_head.json`,
`f2_after.json` and `diff.py` in `/home/david/.cache/cortex-run/2026-11-23/f5/`; `replay.sh`
and `f2replay.sh` take them again.

| | before | after |
| --- | --- | --- |
| rows the message asks to keep that the card lists | 0 | 0 |
| rows newly listed that the message asks to delete, first generator | | 124 |
| rows newly listed that the message asks to delete, second generator | | 104 |
| rows newly listed in the test strings, each holding the value whole | | 75 |
| rows newly listed that the message does not ask for | | 0 |
| rows newly kept | | 0 |
| word pair cases changed | | 0 |

The 75 rows are the five code rows holding `4242` whole beside 15 test strings such as
`Oublie 4242, mon téléphone et la carte aussi.`, each asking for the value and adding a row. Over
the first generator's opening forms, rows asked to delete that the card keeps fell from 23,782
to 23,678; most of the rest are rows holding the value inside a longer value, which the card
keeps by design.

The same rule with the words after the value read by the roles of `beside` (`forget_clauses.py`)
instead of the list above lists 14 more locker rows, none of which the message asks for, in
`Forget 4242, also the card only on the card.` and `Uită 4242 de pe card, și cardul.`: `beside`
drops a limit in the value's own clause and a word naming no stored row.
