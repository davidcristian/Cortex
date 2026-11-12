# Readings: one table for a forget by a card's last group

`inside` (`forget_inside.py`) keeps a row that holds a forget call's text only as the last group of a
longer value, such as `4242` at the end of a card number, unless the person's message points at that
row. Two changes on 2026-11-12 each added a case to that reading
([forget-last-group-beside-whole.md](forget-last-group-beside-whole.md)), and each left a form that
read wrongly: `Forget my gym code.` deleted a card the same chat had just stored, and `Forget my Visa
ending 4242.` beside a gym code `4242` deleted the gym code. This record decides every listing in one
table first and then states the one rule that gets the table right. The decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s.

## The table

The call text is `4242` in every row. The card is `Remember that my card is 4111 1111 1111 4242.`
and the gym code `Remember that my gym code is 4242.`, each stored in chat `chat-a`. "Alone" is the
card with the forget sent from a new chat, "stored" the card with the forget sent from `chat-a`, and
"beside" both rows with the forget sent from a new chat. "Kept" means no row is deleted and the brain
appends a note naming each kept row after the reply. The listings were decided before the code and
are the rows of `test_forget_last_group_table.py`.

| Message | Alone | Stored | Beside | Why |
| --- | --- | --- | --- | --- |
| `Forget my gym code.` | kept | kept | the gym row | `gym` names the gym row; the card is no gym code |
| `Forget 4242.` | the card | the card | the gym row | a value named alone is the row holding it whole, else the only match |
| `Forget the code 4242.` | the card | the card | the gym row | the same, with a code word |
| `Forget my Visa ending 4242.` | the card | the card | kept, both | beside the gym row it may mean either row |
| `Forget the number ending 4242.` | the card | the card | kept, both | the same |
| `Forget my card.` | the card | the card | the card | `card` names the card |
| `Forget what I just told you.` | kept | the card | kept, both | it points at the newest row this chat stored, and a new chat stored none |
| `Forget that.` | the card | the card | kept, both | names nothing; beside the gym row it may mean either |
| `Vergiss, was ich gerade gesagt habe.` | kept | the card | kept, both | the same as `Forget what I just told you.` |
| `Oublie ce que je viens de dire.` | kept | the card | kept, both | the same |

## The rule

A row holding the text only as a last group is listed when the message names a word of that row that
no row holding the text whole has, or a card, an account or an IBAN. Otherwise it is kept when another
row holds the text whole, or when the message lacks the text and names a word, none of the row's and
no function word of a language it is read in. One exception lists it anyway: it is the newest row the
calling chat stored, and the message names no word of any match and no code word (`code_word` in
`memory_values.py`). `Forget what I just told you.` names neither, so it deletes that row, while
`Forget my gym code.` names the code word `code`, which names another fact, so it keeps the card.

When such a row is kept and another match holds the text whole, the message holds the text, and its
words name no match, the whole value row is kept too, under `KEPT_LINE` (`kept_rows` in
`forget_inside.py`). The reader cannot tell which row `Forget my Visa ending 4242.` means, so it keeps
both and the notes name both; the person can then ask again naming one (`Forget my card.`). The
unnamed reader (`unnamed` in `forget_unnamed.py`) reads the kept rows too, so a row kept inside a
longer value still counts as the newest row the chat stored.

## Forms declined on the safe side

- `Forget my Visa ending 4242.` and `Forget the number ending 4242.` beside the gym row keep both rows
  rather than list the card: only `ending` or knowing that a Visa is a card would separate them from
  `Forget my door code 4242.`, and either is a word list.
- `Forget my gym locker.` in the chat that stored the card lists the card. It names no code word, so
  it reads like `Forget what I just told you.`, and only a word list of verbs of saying separates
  them. The card shows the row before anything is deleted.
- `Forget my PIN.` in the chat that stored the card lists it, since a code word alone names no word
  of a fact; the same holds in a new chat, as before this change.

## Replay

Each backticked forget string in `docs/readings/` and the task files, each user message of the
stack's proxy log and the table's messages, 272 strings, ran through the card and the delete of the
start build (`d1620de90`), of `c27485c1e` before this change, and of the change. Each ran on six row
sets (card and gym in both orders, the card alone, an IBAN and a door code, a phone account and a
door code, the phone account alone), from the storing chat and from a new chat, with the string's last
four digits or `4242` as the call text: 3264 cases.

Against `c27485c1e`, 363 cases from 106 strings changed. In 349 the change keeps a strict superset
of the rows, and in none fewer or other rows; the other 14 change only which note names a kept row.
They are of two kinds. In the storing chat, a message naming a code word and no match (`Forget my door
code.`, `Oublie le code de mon casier à la piscine.`) keeps the card, the account or, beside a gym row
stored first, both rows. A message holding the value beside words naming no match (`Forget my bike
lock code 7319.`, `Vergiss 7319, mein Hund ist tot.`) keeps the whole value row as well as the longer
one, where `c27485c1e` deleted the whole value row; asking again with the value alone (`Forget 7319.`)
deletes it. Against the start build, 1636 cases from 236 strings changed, each to a strict superset.
`Forget what I just told you.` deletes the newest row in every row set from the storing chat in all
three builds.

## The live stack: rows and the rule

Written before any draw. The build is `cortexn20-brain-s6table` on port 23069, the working tree with
the change, through the recording proxy, every card approved, `memories` emptied before each draw.
These are the table's riskiest rows: the two the change moves and the two neighbouring flows it must
not move.

| Row | Facts stored | Forget turn | Draws |
| --- | --- | --- | --- |
| s1 | the card, in chat X | `Forget what I just told you.`, in chat X | 3 |
| s2 | the card, in chat X | `Forget my gym code.`, in chat X | 3 |
| s3 | the card and the gym code, each in its own chat | `Forget my Visa ending 4242.`, in a new chat | 3 |
| s4 | the card and the gym code, each in its own chat | `Forget 4242.`, in a new chat | 3 |

The rule: in s1 the card is gone after every draw. In s2 the card is stored after every draw, and
when a call text of `4242` ran, the reply ends with `INSIDE_NOTE` naming the card. In s3 the gym row
is stored after every draw; a call text of `4242` leaves both rows and the reply names both, and a
call text of the whole card number lists the card, which passes and is counted as the form's
frequency. In s4 the card is stored after every draw. A null result is a draw in which no forget call
ran.

## The live stack: what was drawn

Drawn from 02:33 to 02:41 on 2026-11-12 on `cortexn20-brain-s6table`, proxy log lines 658 to 759.
The SM clock read 0.57 of its maximum between draws.

| Row | Call texts in the forget turn | Rows listed | Rows stored after | Pass |
| --- | --- | --- | --- | --- |
| s1 | `4111 1111 1111 4242`, 3 of 3 | the card | none, 3 of 3 | 3 of 3 |
| s2 | `gym code`, 3 of 3, which matched no row | none | the card, 3 of 3 | 3 of 3 |
| s3 | `4242` then `4111 1111 1111 4242`, 2 of 3; `4111 1111 1111 4242` alone, 1 of 3 | none | both, 3 of 3 | 3 of 3 |
| s4 | `4242`, 3 of 3 | the gym row, the card under `INSIDE_LINE` | the card, 3 of 3 | 3 of 3 |

Every item of the rule on stored rows holds, and a forget call ran in all 12 draws. In s1 every
call named the whole number, so the newest row exception was not reached live. In s2 the form
the change is for, a call text of `4242`, occurred in none of the 3 draws, so the note item was not
reached and the unit rows are its evidence. In s3 the call text `4242` kept both rows in 2 of 3
draws, and the reply ended with `KEPT_NOTE` naming both. The expectation that the whole card number
lists the card did not hold: in all 3 draws the unnamed reader kept the card, since `visa` and
`ending` are no words of the card row, and the note named it. That is the safe side the table
declines to, and the person asks again naming the card. Scripts `live.sh`, `calls.py` and `summ.py`
and log `draws.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/d2003893-7ebe-4ec3-ad1c-e92980017fd3/scratchpad/slot6/`.
