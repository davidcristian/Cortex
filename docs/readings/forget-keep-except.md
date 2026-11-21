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
`_EVERY` in `forget_unnamed.py`), so `everything but`, `all but` and `them all but` kept both rows
and showed no card ([since 2026-11-15](forget-everything-but-call.md) only the last does). A `but` after any other word or
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

## A word for but after the forget verb, 2026-11-15

Over `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111 4242.` and
`Remember that my phone is 0721 555 4242.`, with the call text `4242`. Before, `Forget all 4242 but
the card.` deleted all three rows and `Forget 4242 but the card.` deleted only the card, the row
each message asks to keep. `but` opened a keep clause only right after a word for all (`all but`),
since `but quickly` or `but do it now` asks to keep nothing, so the words after it were read as
naming a row to delete.

The reader cannot tell from the words alone whether such a clause asks to keep, so the rows it
names are kept. `after_but` (`forget_clauses.py`) returns the words after `but`, `yet`, `aber`,
`mais`, `pero` or `dar` that follows a forget verb, to the end of the clause, and `kept_rows`
(`forget_inside.py`) keeps each matched row one of them names, by a shared word or a kind of the
table, as it does for a word after a word for minus. It returns no word of a clause that then
holds a forget verb (`but delete the card`), a keep clause (`but keep Anna's phone`, which the
keep clause reader reads) or an adding word (`but the card too`, `but also the card`, `but the
card as well`). Nothing else of the reading changes, so the change deletes no row.

So `Forget all 4242 but the card.` deletes the locker and phone rows and keeps the card, also with
`every`, with a comma before `but`, and with `aber die Karte`, `mais la carte` and `pero la
tarjeta`. `Forget the card 4242, but do it quietly.` still deletes the card,
and `Forget all 4242 but quickly.` all three rows. The tests are `test_forget_after_but.py`.

Kept, and shown as kept, where the message asks to delete: `Forget 4242 but only the card.` and
`Forget the card 4242 but only the card.` keep the card, since no word for only is read ([the role of a named row](#the-role-of-a-row-named-after-the-value-2026-11-15)).
`Forget 4242 but the card.` keeps all three rows, since the locker row is named by no word.

Replay: every string literal of the brain's forget tests, the probes of
[forget-remark-about-the-value.md](forget-remark-about-the-value.md) and the pools and cases of
[forget-added-list.md](forget-added-list.md), through the card without and with the change. Over
the 3,252 cases of the strings that existed before it, 6 cases from 3 strings changed: no row
newly deleted, 14 newly kept. One string is a message, `Forget everything, but my card first.`,
which now keeps the card rows and can be read as asking to; the other two are a reply text and a
result text that hold `but` after `removed` or `forgot`. With the strings of the new tests, 44 of
3,338 cases from 22 strings changed: no row newly deleted, 140 newly kept, each a row the words
after the word for but name. Of 38 further probes, 18 changed, each keeping such a row, among them
`Olvida 4242, voy a dar la tarjeta a mi hermano.`, where `dar` is a Spanish verb and the card row
is kept. Dutch `maar`, Italian `ma` and Polish `ale` are not read, as before. The listings are
`cmp.txt` and `cases5.after3.txt` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/bd106a1a-a17f-4ca5-8841-82294e4917a8/scratchpad/slot3/`.

## Words after the value that no reader reads, 2026-11-15

Over the same three rows and call text. Before, `Forget all 4242 apart from the card.` deleted all
three rows, and so did the same message with `other than`, `besides`, `save`, `aside from`, `with
the exception of`, `without`, `, leave the card` and `, I still need the card`, and `Vergiss alle
4242 bis auf die Karte.` and `Oublie tous les 4242 à part la carte.` over the German and French
rows. `Forget 4242 apart from the card.` and `Forget 4242 not the card.` deleted only the card.
No reader holds these phrases, so `card` named a row to delete.

No phrase was added. A row the message names after the value is now listed only when a reader
reads every word before its name. `after_value` (`forget_clauses.py`) takes each run of words
after the first place the message holds the call's text, to a clause mark or a forget verb. Up to
the last word naming a matched row, a word is read when it names a matched row by the row's
request, or is a number, a code word, a word for and or or, a placing word (`on`, `of`, `for`,
`from`, `in`, `at`, `de`, `du`, `sur`, `pour`, `dans`, `auf`, `von`, `vom`, `für`, `del`, `en`,
`para`, `pe`), a word for the or my, or an identifying word (`it`, `that`, `which`, `this`, `is`,
`was`, `I mean`, `only`, `just`). From the first word that is none of these, the words may ask to
keep the rows they name, and `kept_rows` (`forget_inside.py`) keeps those rows under `KEPT_LINE`.
A negation after the last row name does the same for the whole run, as in `the card not`. A run
holding an adding word or a keep clause is left to the readers of those. Nothing else of the
reading changes, so the change deletes no row.

So each message above with a word for all deletes the locker and phone rows and keeps the card.
`Forget 4242 apart from the card.` keeps all three rows, since no word names the locker or the
phone. A message in a language the card does not read keeps a row it names by a word the card
reads: `Verwijder alle 4242 behalve de card.` keeps the card. Still deleted: the card for `Forget
4242 on the card.`, `Forget 4242, my card.`, `Forget 4242, only the card.`, `Forget 4242, that is
my card.`, `Oublie le 4242 de ma carte.` and `Șterge 4242 de pe card.`, the phone for `Forget
4242, and the phone.`, and all three rows for `Forget the card 4242, the phone and the locker
too.`. The tests are `test_forget_after_value.py`.

Replay: every string literal of the brain's forget tests, the backticked messages of the
`forget-*.md` readings, the pools of the two sections above and 115 probes written for this
change, each over the three English rows and over 18 rows in five languages, through the card
without and with the change. Over the 4,750 cases of the strings that existed before the new
tests, 80 cases from 43 messages changed: no row newly deleted, 230 newly kept. Of those rows,
180 from 30 messages are rows the message asks to keep: the phrases above, `Forget 4242 not the
card.`, and `ohne`, `abgesehen von`, `hors`, `à l'exception de`, `aparte de`, `a excepción de`,
`în afară de` and `cu excepția`. 32 rows from 10 messages are named in a remark that can be read
either way, such as `Forget 4242 that I texted from my phone.` and `Forget 4242, I cancelled the
card.`. 18 rows from 3 messages are rows the message asks to delete, kept and shown as kept:
`Forget 4242, it is my old card.`, `Forget 4242, it is the end of my phone number.` and `Forget
all 4242 including the card.`, where no reader reads `old`, `end` or `including`. With the
strings of the new tests, 91 of 4,814 cases changed: no row newly deleted, 267 newly kept. The
listing is `cmp_full.txt` in `/home/david/.cache/cortex-run/2026-11-15/slot4/`.

## The role of a row named after the value, 2026-11-15

Over the same three rows and call text. Before, `Forget all 4242 on the card.` and `Forget all
4242, only the card.` deleted all three rows, `Forget all 4242, card stays.` deleted the card, and
`Forget all 4242 but only the card.` deleted the locker and the phone. `beside`
(`forget_clauses.py`) reads each run after the value as a limit, an addition or an exception. A
run holding a word none of those readers reads, or followed by a clause naming no row that holds
one, has no role, and the card keeps every row the words before the value do not name. Replay as
above, 5,008 cases with the strings of this change: 255 changed, no row newly deleted, 1,696 newly
kept. By hand over the three English rows (135 cases, 251 rows): 92 rows the message asks to keep,
18 either way, 141 the message asks to delete, most after a phrase no reader reads (`Forget all
4242 apart from the card.` keeps all three). Keeping only the named row of an unread role left 26
rows of 13 limit messages listed, such as the locker and phone of `Forget all 4242 solely on the card.`.
The listings are `cmp_final.txt` and `class_final.txt` in `/home/david/.cache/cortex-run/2026-11-15/slot5/`. A row named to forget and again to keep, the same day: `Forget the card 4242, card stays.` and `Forget the card 4242, keep the card.` listed the card, and `_restated` (`forget_inside.py`) now keeps it. Replay as above, 5,042 cases: 31 changed, no row newly deleted, 91 newly kept, none a row its message asks to delete. A generator of 42,356 messages (4 opening forms, then one or two of 7 kinds of clause over the 3 rows, in the 5 languages, and the values `tulip`, `12 34` and `card`): the cases listing a row the message asks to keep went from 9,140 to 1,248, with no row newly listed and 8,320 newly kept, 214 of them rows the message asks to delete, as the card of `Forget the card 4242, the card too and the phone.`. Each of the 1,248 joins a second phrase to a keep form with no clause mark. The same day `_restated` keeps a row a keep clause names again beside words that each name another row, and `_runs` (`forget_clauses.py`) reads the words between the value and a keep clause of the same clause as a run of their own, from which `beside` reads only an exception or an unread role. Replay over the 5,050 cases the two trees share: none changed. Generator: the 1,248 went to 135, with no row newly listed and 1,906 newly kept, 548 of them rows the message asks to delete, as the locker of `Forget all 4242, the card stays except the phone.`. Of the 135, 96 hold a keep clause naming the row beside `only` or `seulement` ([task 1216](../refinements/tasks/1216-a-keep-clause-naming-the-row-to-forget-beside-a-word-for-only-lists-it.md)), 35 name a Romanian row with its article ([task 1217](../refinements/tasks/1217-a-romanian-row-named-with-its-article-in-a-keep-clause-names-no-row.md)) and 4 have the value `card` ([task 1218](../refinements/tasks/1218-a-forget-whose-value-is-a-word-of-the-row-lists-a-row-the-message-keeps.md)). Of the generator's 1,604 messages of at most one clause, 602 keep a row the message asks to delete, before and after: a word for only, also or all that the card reads in English is unread in other languages ([task 1221](../refinements/tasks/1221-the-forms-the-forget-card-reads-in-english-are-not-all-read-in-the-other-four-languages.md)). Those listings are `mix_t0.json` and `mix_t2.json` in `/home/david/.cache/cortex-run/2026-11-15/slot7/`. Each row kept under an unread role was shown under a reason untrue for it, as the phone of `Forget the locker 4242 including the phone.` under "your message names none of their words or asks to keep them". The card line and the reply note (`KEPT_LINE`, `KEPT_NOTE`) now say that the message was not read as meaning the rows, in the five note languages, and still ask for nothing. The result texts the model reads still give the old reason ([task 1219](../refinements/tasks/1219-the-result-texts-a-model-reads-give-an-untrue-reason-for-a-row-kept-under-an-unread-role.md)), and neither text says how to ask for a kept row ([task 1220](../refinements/tasks/1220-the-kept-note-does-not-say-how-to-ask-for-a-row-it-names.md)). The listings are `cmp.txt`, `mix_before.json` and `mix_after.json` in `/home/david/.cache/cortex-run/2026-11-15/slot6/`. On 2026-11-21 `_restated` reads where each other word of the keep clause is: a word naming no row stops the keep only before the word naming the row again, as `need` of `I don't need the card`. Generator: the 135 went to 18, the 96 beside `only` or `seulement` and 21 of the 35 Romanian ones, with no row newly listed and 117 newly kept, none a row its message asks to delete. Of 5,979 calls over the strings of the brain's forget tests, each string with its value, `card` and `phone` as the call text, 4 changed, all of `Forget the card 4242, keep the card statement.` and `Forget the card 4242, keep the card and the statement.`, which now keep the card each asks to delete. The listings are `cmp1.txt`, `full_before.json` and `full_after1.json` in `/home/david/.cache/cortex-run/2026-11-21/f1/`.

## A language the card does not read, 2026-11-15

Over the same three rows and call text. `Verwijder alle 4242 behalve de kaart.` and `Verwijder
alle 4242 maar de kaart.` delete all three rows: `alle` is a German word for all, and no word of
either message names a row or is read by a reader. The forget tool needs the person's approval
(`confirm_required`), and its card lists the three rows under `Deletes for good, with no undo,
these 3 remembered exchanges:` before any delete, with no kept line, so the card row is in the
list the person approves.

Declined 2026-11-15, with no Dutch word added. `behalve de kaart` names no row by a word the card
reads, and neither does `but quickly`, `aber schnell`, `mais vite` or `pero rápido` after a word
for all and the value. Each of those four deletes all three rows, and `test_forget_after_but.py`
asserts it of `Forget all 4242 but quickly.`. A shape keeping every listed row when a content
word after the value names no row was
replayed over the strings of the section above, 4,832 cases with its own messages: 510 cases
changed and 2,272 rows were newly kept, among them all three rows of those four messages and the
card of `Forget the card 4242, but do it quietly.`. The shape of the section above covers the
form once a word the card reads names the row: `Verwijder alle 4242 behalve de card.` keeps the
card.

Of 38 forget requests in Italian, Portuguese, Dutch and Polish replayed through the card without
and with the change of the section above, 4 list fewer rows, each keeping a card named after a
word the card does not read (`tranne la card`, `oprócz card`, `behalve de card`, `behalve mijn
card`). The other 34 list the same rows, among them every request naming a value alone:
`Verwijder alle 4242.` deletes all three rows and `Dimentica 4242.` keeps them, as before. The
listing of the declined shape is `cmp_a.txt` in `/home/david/.cache/cortex-run/2026-11-15/slot4/`.
