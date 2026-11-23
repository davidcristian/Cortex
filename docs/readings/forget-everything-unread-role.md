# Readings: a forget of everything naming a row in a role no reader reads

How the forget card reads a message that asks to forget everything and then names a stored row in
words no reader reads, such as `Forget everything, my card stays.` (`message_rows` in
`forget_permit.py`). The decision is [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s. The
same rule for a row named after a value is in
[forget-keep-except.md](forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15).

## Every row kept under an unread role, 2026-11-15

Over `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111 4242.` and
`Remember that my phone is 0721 555 4242.`. Before, a call naming the card deleted it:

| Message | Call text | Before | After |
| --- | --- | --- | --- |
| `Forget everything, my card stays.` | `card` or `4242` | the card | none |
| `Forget everything, leave my card.` | `card` or `4242` | the card | none |
| `Forget everything apart from the card.` | `card` or `4242` | the card | none |
| `Forget everything, the card stays, the phone too.` | `phone` | the phone | none |
| `Oublie tout, la carte reste.` | `carte` | the card | none |
| `Olvida todas, deja la tarjeta.` | `tarjeta` | the card | none |
| `Forget everything on my card, the phone stays.` | `phone` | the phone | none |
| `Forget everything on my card, the phone stays.` | `card` | the card | the card |

No verb for stays and no phrase for except was added. The words after the word for all are split
into runs as the words after a value are, and a run naming a stored row with a word that no
reader of a limit, an addition or an exception reads has no role. The three roles list different
rows, so the card lists only a row a read limit names and that run does not.

These list what they listed before, with every call text: `Forget everything.`, `Forget
everything but my card.`, `Forget everything except my card.`, `Forget everything, also the
card.`, `Forget everything, only the card.`, `Forget everything on my card.`, `Forget everything
about my gym.`, `Forget everything I told you today.`, `Forget all of that.`, `Forget the card
that stays in my wallet.`, `Forget what stays the same.` and `Forget all my card numbers.`.

## The replay

The messages and call texts of
[the earlier replay](forget-everything-but-call.md#the-message-permits-and-the-call-selects-2026-11-15):
24,555 messages with 171,769 calls, the 42,356 generated messages with the value as the call
text, 5,400 test strings and 61 requests in Italian, Portuguese, Dutch and Polish with 305 calls.

| Count | Before to after |
| --- | --- |
| Rows newly listed, every replay | 0 |
| Rows listed that the generator marks asked to keep | 3,808 to 689 |
| Rows newly kept that it marks asked to keep | 3,119 |
| Rows newly kept that it marks either way | 838 |
| Rows newly kept that it marks not asked | 1,760 |
| Rows newly kept that it marks asked to delete | 4,827 |
| Value calls over the generated messages that changed | 0 of 42,356 |
| Test strings that changed, each keeping more rows | 4 of 5,400, 12 rows |
| Calls in the four unread languages that changed | 0 of 305 |

The 4,827 rows are the other rows of the same messages: `Forget everything, the card stays.`
with the call text `phone` kept nothing before and keeps the phone now, since a limit to the card
would keep it. A separate set of 172 messages holding no value, in the five languages with six
call texts each, lists 302 rows asked to keep before and 83 after. The 83 are under a word for
all the card does not read (`alles`, `todo`, `toate`, `tot`), which is filed with two English
forms that still list the card: no clause mark before the row (`Forget everything my card
stays.`) and a verb the card does not read as a forget (`Wipe everything, my card stays.`).

## A topic word that ends its clause, 2026-11-15

`everything` read no word for all followed by a topic word (`about`, `else`, `sur`, `über`,
`sobre`), so `Forget everything else, my card stays.` deleted the card for the call text `card`
or `4242`. A topic word that ends its clause opens no topic, so the word for all before it is
now read, and that message and `Forget all else. My card stays.` keep every row. `Forget
everything else.`, `Forget everything else about my card.` and `Forget everything else, also the
card.` list what they listed before. No word was added to a set.

Replayed over the messages above, the build before the change against the tree: 0 rows newly
listed and 0 calls changed among the 171,769 calls, the 42,356 value calls, the 1,032 calls of
the 172 messages holding no value and the 305 calls in the four unread languages. Of 5,514 cases
of the test strings, 2 changed, both `Forget everything else, my card stays.` keeping the card.

## Drawn after the card changes, 2026-11-15

The stack brain `cortexn23-brain-1` rebuilt from the commit holding the day's card changes up to
the reasons for the four unread cells (the rows the message permits, the table of forms and
every row kept under an unread role), engine build `b12375-9d25e0014`, default `judge` recall,
through the recording proxy (lines 786 to 851). Four exchanges were stored once through the
model, `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111 4242.`,
`Remember that my phone is 0721 555 4242.` and `Remember that my gym code is 7391.`, and the
same four rows were copied back into `memories` before each draw. One message a draw in a new
chat, every card approved. The SM clock read 0.58 of its maximum before and after.

| Message | Draws | Forget calls | Rows the cards list | Listed rows the message keeps | Rows to delete left stored | Untrue sentences |
| --- | --- | --- | --- | --- | --- | --- |
| `Forget everything but my card.` | 3 | 9: `locker code`, `phone` and `gym code` in each draw | 9 | 0 | 0 | 0 |
| `Forget all 4242 except the card.` | 2 | 4: `locker code` and `phone` | 4 | 0 | 0 | 0 |
| `Forget everything, my card stays.` | 2 | 0 | 0 | 0 | 6 | 2 |
| `Forget my gym code.` | 2 | 2: `7391` | 2 | 0 | 0 | 0 |
| `Uită tot în afară de card.` | 2 | 0 | 0 | 0 | 6 | 2 |
| `What is my locker code?` | 1 | 0 | 0 | 0 | 0 | 0 |

No card listed a row its message keeps, and each card listed the one row its call named. The
second message left the card and the gym code stored. The recall turn answered `Your locker code
is 4242.`

The third and fifth messages deleted nothing. Their first requests held the card row alone:
recall ranked it, and `with_forget_reach` adds the nearest rows only beside a keep clause that
`asks_to_forget_keeping` reads. The model made no call and wrote `I've cleared all other memories
while keeping your card information` and `am păstrat doar informația despre cardul tău și am
șters restul memoriilor`. Each English reply ended with `UNFORGOTTEN_CLAIM_NOTE` and each
Romanian one with `UNCALLED_FORGET_NOTE` in Romanian, after `UNKEPT_CLAIM_NOTE`, which the
reply's `Am reținut.` made due. So each of the four untrue sentences is followed by a true note
that nothing was deleted. In a unit call the card keeps every row of the third message with any
call text, and lists the card for the fifth with the text `card` or `4242`, since `tot` is not
read. Both are filed. Logs `*.jsonl`, `*.log` and `*.left.txt` in
`~/.cache/cortex-run/2026-11-15/slot14/`; scripts `draws.sh` and `probe.py` in
the `slot14` scratch directory of the 2026-11-15 run.

## The day's four card changes replayed together, 2026-11-15

The build before the rows the message permits, the build holding only that change and the
build holding all four, over the pools above. From the first to the second, 0 of 73,579 calls
whose text holds a digit changed, 0 of 54,461 calls of a text holding no digit beside a message
holding no value changed, and the value calls and the test strings gave the same bytes. From the first to the last, 0
rows are newly listed among the generated messages. The word sets of `forget_clauses.py` built
before the table of forms and after it are the same but for `toute`, `jede`, `jeden` and
`jedes`. Those four list 82 rows of the test strings, each asked for.

## A row named between a word for all and the value, 2026-11-15

`Forget every card 4242.` listed the locker code and the phone with the card, and so did each
word for all of the table of forms. `quantifies` (`forget_unnamed.py`) now reads the rows: a word
between the word for all and a value after it that names a matched row, or is a kind word, stops
the word for all asking for every row, so the message reads as `Forget the card 4242.` does. A
limit after the value still keeps the rows it does not name, as in `Forget every locker 4242 on
the card.`. Replayed before and after:

| Replay | Calls | Newly listed | Newly kept |
| --- | --- | --- | --- |
| generated pools, every call text | 171,769 | 0 | 0 |
| value calls, the keep readers and the forms of everything | same bytes | 0 | 0 |
| `Vergeet jede card 4242.` in the unread languages | 4 of 305 changed | 0 | 5, none asked for |
| word for all, row word, value, with each tail | 135,135 | 0 | 7,290 |

The last row is 19,305 messages over the generator's rows in five languages: each word for all
of the table, then a row word bare or with its article, then `4242`, alone and with each tail. Of
the 7,290 rows newly kept, 6,930 are not asked for, 120 are asked to keep, 0 are either way and
240 are asked to delete, each after an adding word no reader reads, as in `Uită all cardul 4242,
dulapul de asemenea.`. Two forms still list a row the message does not ask for, and both are
filed. A row word in a form no stored row holds is not read: 600 rows of the Romanian `dulapul`,
and `Forget all lockers 4242.`. A call text holding a digit the message lacks lists the row it
names: 1,440 rows, the same before and after. Scripts `kindgen.py`, `kindsum.py` and `replay.sh`
in the `slot15` scratch directory of the 2026-11-15 run.

## A word for all after a named row and its value, 2026-11-20

`Forget the card 4242 everywhere.` listed the locker code and the phone with the card, and with
the call text `phone` it listed the phone. `quantifies` now reads the words before a value that
a word for all follows (`before_every` in `forget_kinds.py`): back to a forget verb or a word for
and, a word naming a matched row, or a kind word, stops the word for all asking for every row.
`Forget all lockers 4242.` listed all three rows, since no row holds `lockers`. `limited` now
reads a word that a word of a matched row starts as that row's word, and the reader of a last
group (`_ends` in `forget_inside.py`) reads the matched rows too, so the message keeps every
row, as `Forget the lockers 4242.` does. The safe direction is keeping a row. Replayed before
and after, each message with the value as the call text and each test string with three call
texts:

| Replay | Calls | Changed | Newly listed | Newly kept |
| --- | --- | --- | --- | --- |
| generated heads and tails in five languages | 42,356 | 0 | 0 | 0 |
| string literals of the brain's forget tests | 5,865 | 0 | 0 | 0 |
| a row named, the value, then a word for all | 450 | 450 | 0 | 930 |
| a word for all, a longer form of a row word, the value | 225 | 135 | 0 | 405 |
| a word for all, a row word, the value | 225 | 15 | 0 | 45 |
| a word for all beside the value alone | 600 | 0 | 0 | 0 |

The last four rows are 1,500 messages over the generator's fifteen rows and the fifteen words
for all of the table of forms. The first change alone keeps 840 rows, each one the message may
mean either way, and changes no other row of the table. Of the 1,380 rows newly kept by both,
1,035 are rows the message may mean either way, 300 are not asked for, none is asked to keep
and 45 are asked to delete. The 45 are one row, the locker code holding `dulap`, named as
`dulapul` before or after a word for all: `Uită dulapul 4242.` with no word for all already
kept it, since the card does not read the Romanian article. The 90 longer forms that changed
nothing are kind words of the table, such as `cards` and `Karten`, which listed their one row
before. The string literals are replayed over the generator's fifteen rows, which hold no
bike lock, so the four test strings that name one (`Forget my bike lock code 7319 everywhere.`
and three more) change only in their own tests: each now keeps the shed padlock code, a row the
message may mean either way. A word no stored row word starts still lists every row, as in
`Forget all cupboards 4242.`, and is filed. Scripts `gen.py`, `mkcases.py`, `run.py` and
`cmp.py` in `~/.cache/cortex-run/2026-11-20/forget-replay/`.

## The four blocked cells replayed, 2026-11-15

With every row kept under an unread role, `toate`, `doar`, `seulement` and `también` were each
filled alone in the table of forms (`forget_forms.py`) and replayed over the same messages. Rows
newly listed, by what the generator marks:

| Cell filled | Replay | Asked to delete | Either way | Not asked | Asked to keep |
| --- | --- | --- | --- | --- | --- |
| `toate` | every call text | 480 | 0 | 40 | 26 |
| `toate` | value call | 427 | 0 | 54 | 22 |
| `doar` | every call text | 270 | 83 | 18 | 8 |
| `doar` | value call | 471 | 160 | 49 | 8 |
| `seulement` | every call text | 1,179 | 279 | 272 | 0 |
| `seulement` | value call | 854 | 316 | 76 | 0 |
| `también` | every call text | 811 | 69 | 14 | 0 |
| `también` | value call | 838 | 160 | 28 | 0 |

No cell is filled, since a cell is filled only when no row newly listed is kept or not asked. The
rows `toate` lists that the message keeps are named with the Romanian article, which names no
stored row: `Uită toate, dulapul rămâne, și cardul.` with the call text `dulap`, and `Uită toate
4242, dulapul rămâne.` by value. `doar` lists the card of `Uită toate, cardul rămâne, doar
cardul.` while `toate` is unread, and the locker code of `Uită 4242 doar de pe dulap exceptând
dulapul.`. `seulement` and `también` list no row the message keeps. Their rows not asked are
beside an added or kept row: `Oublie tous les 4242, la carte aussi, seulement le téléphone.` lists
the locker code, as English `only` does, and `Olvida 4242, el teléfono también, solo la tarjeta.`
lists the phone, since `solo` is unread. Filled, `doar` also changes the Polish `Zapomnij 4242,
doar card.`, 2 of 305 calls in the four unread languages; the other three cells change none. Of
the 1,604 generated messages of at most one clause, 602 keep a row asked to delete with no cell
filled, and 577, 584, 580 and 588 with `toate`, `doar`, `seulement` and `también` filled.
