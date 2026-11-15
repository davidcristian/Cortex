# Readings: a word for except opening a keep clause of a forget

How `unnamed` (`forget_unnamed.py`) reads a forget message whose clause asking to keep opens with a
word for except, such as `Forget the code 4242 except the card.`, or with `but` right after a word
for all, such as `Forget everything but my card.`. The other keep clause forms are in
[forget-keep-clause.md](forget-keep-clause.md). The decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s.

## A word for except, 2026-11-11

Unit calls over two rows holding 4242, `User: My card is 4111 1111 1111 4242.` and
`User: Code 4242.`, with the call text `4242`. Before, `Forget the code 4242 except the card.` and
`Forget everything except my card.` opened no keep clause: the reader named the card row by `card`
and kept only the code row, so the card listed the row the person asked to keep. A clause now also
opens at `except`, `excluding`, `sauf`, `hormis`, `excepté`, `außer`, `ausgenommen`, `excepto`,
`salvo` and `exceptând`, and that word names no fact to keep. Both messages now keep both rows and
show no card, the same as `Forget the code 4242, keep the card.` and `... but not my card.`, since
`code` names any code and no whole word outside the clause names a row. `Forget my bike code 4242
except the card.` lists only the bike row. `moins`, `menos` and `mai puțin` open no clause, since
each can also mean minus or less; the Romanian `cu excepția` and `în afară de` and an ASCII
`ausser` are left out. `exception` and `excepted` open no clause. The tests are
`test_forget_keep_except.py`.

Replay: 541 distinct forget strings (the user messages of the night's recording proxy log and every
backticked forget string in `docs/readings/` and the task files) over seven rows holding the
string's last number, with that number and `code` as call texts. 4 cases from 2 strings changed,
both the messages above, and none keeps fewer rows. Script `replay.py` and log `replay.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/f3217b06-cdcf-4ffa-92c2-cc5df81e7d11/scratchpad/slot21/`.

## But after a word for all, 2026-11-12

Unit calls over the same two rows with the call text `4242`. Before, `Forget everything but my
card.` and `Forget all but my card.` opened no keep clause, since `but` opens one only before a
negation: the reader named the card row by `card`, kept only the code row, and the card listed the
row the person asked to keep. `but` now also opens a clause right after a word for all (`_BUT` and
`_EVERY` in `forget_unnamed.py`), so `everything but`, `all but` and `them all but` keep both rows
and show no card, the same as `Forget everything except my card.`. A `but` after any other word or
after a clause mark opens none, so `Forget my card 4242, but quickly.`, `Forget all of my card 4242,
but quickly.`, `Forget everything, but my card first.`, `Forget all my card numbers but quickly.`,
`Forget it but quickly.` and `Forget 4242 but do it now.` read as before. A misread such as
`Forget all but quickly.` opens a clause naming no row, which keeps every row. The tests are in
`test_forget_keep_except.py`.

Replay: 995 distinct forget strings (234 backticked in `docs/readings/` and the task files, 761
more from the string literals of the brain's tests) over eight rows holding the string's last
number, with that number and `code` as call texts, with and without the calling chat's row.
4,975 cases; 15 changed from 3 strings, `Forget everything but my card.`, `Forget all but my card.`
and `Forget them all but my card.`, and none keeps fewer rows. Scripts `strings.py`,
`replay_one.py`, `diff.py` and log `replay.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/d2003893-7ebe-4ec3-ad1c-e92980017fd3/scratchpad/slot1/`.

### Neighbouring flows on the live stack: rows and the rule

Written before any draw. The build is the working tree with the change, run as a second brain
through the recording proxy on the `cortexn20` stack, a new chat for each turn, every card
approved, and every row deleted before each draw. Each row stores its facts in one chat per fact.

| Row | Facts stored | Forget turn | Draws |
| --- | --- | --- | --- |
| j1 | `My locker code at the pool is 7319.` | `Actually, forget what I just told you.`, same chat | 4 |
| v1 | `Remember that my card PIN is 7319.`, `Remember that my door code is also 7319.` | `Forget 7319.` | 4 |
| b1 | `Remember that my card is 4111 1111 1111 4242.`, `Remember that my gym code is 4242.` | `Forget everything but my card.` | 4 |
| b2 | as b1 | `Forget all but my card.` | 4 |

The rule: in b1 and b2 no card lists the card row and the card row is stored after every draw. In
j1 every draw that calls a forget tool deletes the locker row. In v1 every draw that calls a forget
tool with the text `7319` deletes both rows. A draw with no forget call is counted apart and fails
no item, since the change reaches only the reader of a call's message.

### Neighbouring flows on the live stack: what was drawn

Drawn from 00:28 to 00:38 on 2026-11-12, the working tree as `cortexn20-brain-s1fix` through
`cortexn20-proxy`, proxy log lines 6 to 144. The SM clock read 0.57 of its maximum between draws.

| Row | Draws with a forget call | Rows the card listed | Rows stored after |
| --- | --- | --- | --- |
| j1 | 4 of 4, text `7319` | the locker row, 4 of 4 | none, 4 of 4 |
| v1 | 4 of 4, text `7319` | both rows, 4 of 4 | none, 4 of 4 |
| b1 | 0 of 4 | no card | both rows, 4 of 4 |
| b2 | 0 of 4 | no card | both rows, 4 of 4 |

Every item of the rule holds. In b1 and b2 the change is not reached, since no draw called a forget
tool: recall ranked only the card row as helping with the message, so the first request named only
that row, and 7 of the 8 replies said the card was the only memory stored while the gym row was
stored, with no note ([forget-keep-no-call.md](forget-keep-no-call.md)). The eighth said other memories were cleared and ended with the
note that nothing was forgotten. Script `live.sh` and log `live.log` in the slot directory above;
the stack is described in `stack.md` one directory up.

## A word for all beside a keep clause of kind words, 2026-11-15

Over `Remember that my locker code is 4242.`, `Retiens que ma carte est 4111 1111 1111 4242.` and
`Remember that my phone is 0721 555 4242.`, with the call text `4242`. Before, `Forget every 4242
except the card.` listed only the locker row: beside a keep clause a value alone listed a row only
by its whole value, and the phone row holds `4242` as the last group of a longer value.

A wider shape, every row the keep clause does not name, was replayed first and not kept. For
`Forget every 4242 except the phone.` it deleted `Merke dir, mein Handy ist 0721 555 4242.`, a row
the message asks to keep, since no word of the kind table reads `Handy` as a phone. It also deleted
a row holding `4242` as an amount or only in its reply.

`unnamed` now lists a row holding the value as the last group of a longer whole value when all of
these hold (`_other_kinds` and `_lists` in `forget_unnamed.py`): a word for all is beside the value
(`quantifies`), no word for all is inside a keep clause, no code word is outside one, each content
word of the keep clause is a word of the kind table (`forget_kinds.py`), and the row names a kind
of that table. A row the keep clause names is kept as before. So the message above deletes the
locker and phone rows and keeps the card, in English, French, German and Spanish, and `Forget 4242,
except the card.` still lists only the locker row.

Kept as before: a badge `9000 4242` and the `Handy` row, which name no kind of the table; every row
for `except the passport`, which names no row; the phone for `except every card`, `except all the
cards`, `every code 4242 except the card` and `everything about 4242 except the card`; and every
row for `Șterge toate 4242 exceptând cardul.`, since `EVERY` has no Romanian word. `Forget every
4242 but keep the card.` also keeps the phone, since `quantifies` reads no clause holding a keep
verb ([task 1204](../refinements/tasks/1204-a-word-for-all-in-a-clause-holding-a-keep-verb-keeps-a-last-group-of-another-kind.md)).
The tests are `test_forget_every_except.py`.

Replay: the strings, pools and cases of [forget-added-list.md](forget-added-list.md), through the
card with that change and with this one added. 20 cases from 10 strings changed, each a message
with a word for all beside a keep clause of kind words. 60 rows are newly deleted and none newly
kept: each is a card or phone row, in one of the five languages, of the kind the keep clause does
not name. The listing is `cmp2.txt` in `/tmp/claude-1000/-home-david-Files-Git-Cortex/bd106a1a-a17f-4ca5-8841-82294e4917a8/scratchpad/slot2/`.
