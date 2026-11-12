# Readings: a forget by a code that a longer value ends with

On 2026-11-12 the `cortexn20` stack stored `Remember that my card is 4111 1111 1111 4242.` and
`Remember that my gym code is 4242.`. `Forget my gym code.` then called `forget_memories` with the
text `4242` in one of three draws, and the approved card deleted both rows
([forget-keep-no-call.md](forget-keep-no-call.md#a-forget-with-no-keep-clause-what-was-drawn)).
`inside` (`forget_inside.py`) kept a row holding a code as one group of a longer value, but never
as its last group, since a card is named by its last four digits. The decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s.

## The change and its unit rows

A row that holds the call's text only as the last group of a longer value is now also kept under
`INSIDE_LINE` when another row holds the text as a whole value and the message names no word of
the row that the whole-value rows lack. A row the calling chat stored last stays listed when the
message names no word of any row, since that row is what the person just said. With no row
holding the text whole, a last group is listed as before. The rows are in
`test_forget_group_beside_whole.py`, card and gym code stored in that order unless named:

| Message | Lists | Kept | Why |
| --- | --- | --- | --- |
| `Forget my gym code.` | the gym row | the card, `INSIDE_LINE` | `gym` names the gym row only |
| `Forget the code 4242.` | the gym row | the card, `INSIDE_LINE` | no word, and the gym row holds `4242` whole |
| `Forget 4242.` | the gym row | the card, `INSIDE_LINE` | a value named alone is that value, not a card's end |
| `Forget what I just told you.`, gym stored last in the chat | the gym row | the card, `INSIDE_LINE` | the newest row is the gym code |
| `Forget what I just told you.`, card stored last in the chat | the card | the gym row, `KEPT_LINE` | the newest row is the card |
| `Forget the card ending in 4242.` | the card | the gym row, `KEPT_LINE` | `card` names the card |
| `Forget my Visa 4242.`, a row `my Visa is 4111 1111 1111 4242` | the Visa row | the gym row, `KEPT_LINE` | `visa` is a word only that row has |
| `Forget the gym code I asked you to remember.` | the gym row | the card, `INSIDE_LINE` | both rows hold `remember`, so it names neither |

**Replay.** Every backticked forget string in `docs/readings/` and the task files, and every user
message of the stack's proxy log, 251 strings, ran through the card and the delete of the start
build and of the change. Each string ran on five row sets (card and gym in both orders, the card
alone, an IBAN and a door code, a phone account and a door code), from the chat that stored them
and from a new chat, with the string's last four digits or `4242` as the call text: 2510 cases.
972 cases from 200 strings changed, and none kept fewer rows: each change keeps the longer value
row, or changes only the card's wording. The card alone changed in no case.

## Neighbouring flows on the live stack: rows and the rule

Written before any draw. The build is `cortexn20-brain-s4beside`, the working tree with the change,
through the recording proxy, every card approved, `memories` emptied before each draw. Each fact is
stored in its own chat and the forget sent in a new chat, except j1, which stores both facts and
sends the forget in one chat.

| Row | Facts stored, in order | Forget turn | Draws |
| --- | --- | --- | --- |
| g1 | the card, the gym code | `Forget my gym code.` | 4 |
| v1 | the card, the gym code | `Forget 4242.` | 4 |
| e1 | the card, the gym code | `Forget the card ending in 4242.` | 4 |
| j1 | the card, the gym code, one chat | `Forget what I just told you.` | 4 |

The rule: in g1, v1 and j1 the card row is stored after every draw, and in e1 the gym row is.
A draw passes when its forget turn leaves that row. Which rows each call text listed is recorded;
a draw whose call names the whole card number fails no item, and counts the form's frequency. A
null result is a draw in which no forget call ran.

## Neighbouring flows on the live stack: what was drawn

Drawn from 01:43 to 01:54 on 2026-11-12 on `cortexn20-brain-s4beside`, proxy log lines 406 to 585.
The SM clock read 0.57 of its maximum between draws.

| Row | Call texts | Rows listed | Row stored after | Pass |
| --- | --- | --- | --- | --- |
| g1 | `gym code`, 4 of 4 | the gym row | the card, 4 of 4 | 4 of 4 |
| v1 | `4242`, 4 of 4 | the gym row, the card under `INSIDE_LINE` | the card, 4 of 4 | 4 of 4 |
| e1 | `4111 1111 1111 4242`, 3 of 4; `4242`, 1 of 4 | the card; for `4242` the gym row under `KEPT_LINE` | the gym row, 4 of 4 | 4 of 4 |
| j1 | `gym code` twice, `gym code is 4242`, `4242` | the gym row; for `4242` the card under `INSIDE_LINE` | the card, 4 of 4 | 4 of 4 |

Every item of the rule holds, and a forget call ran in all 16 draws. The form the change is for, the
text `4242` with a gym code row matched, occurred in 5 of the 12 g1, v1 and j1 draws, and each kept
the card. Scripts `live.sh` and `summ.py` and logs `draws.log` and `draws2.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/d2003893-7ebe-4ec3-ad1c-e92980017fd3/scratchpad/slot4/`.

## A last group with no row holding the code whole

With only `Remember that my card is 4111 1111 1111 4242.` stored, `Forget my gym code.` with the call
text `4242` listed and deleted the card: no other row held `4242` whole, so the rule above did not
apply. A row holding the call's text only as a last group is now also kept when the message does
not hold the text and names at least one word, none of them a word of that row. The newest row the
calling chat stored is still listed when the message names no word of any match. When the person
writes the digits, they name the last group themselves, so the row is listed as before.

A kept row reaches the person. On a card it is shown under `INSIDE_LINE`. A call whose every match
is kept this way shows no card and returns `INSIDE_ALL`, and the brain appends `INSIDE_NOTE`
(`inside_note`, in the note language) after the reply, naming the row. Its text, that the searched
text is only part of a longer value in the row, is true of every row this rule keeps.

The rows are in `test_forget_group_alone.py`: the card alone, the call text `4242`, from a new chat
unless the storing chat is named. Each listing was decided before the code was written.

| Message | Result | Why |
| --- | --- | --- |
| `Forget my gym code.` | kept, `INSIDE_NOTE` | lacks `4242`, and `gym` is no word of the card |
| `Oublie mon code de gym.` | kept | the same in French |
| `Forget my Visa.` | kept | `visa` is no word of the card row; the note names the card, so the person can ask again |
| `Forget what I just told you.` | kept | this chat stored nothing, and `told` is no word of the card |
| `Forget what I just told you.`, storing chat | listed | the newest row the chat stored, no word of any match named |
| `Forget my gym code.`, storing chat | listed | read like the row above, since `gym` names no match; filed as task 1156 |
| `Forget the code 4242.` | listed | the message holds `4242` |
| `Forget 4242.` | listed | the message holds `4242` |
| `Forget the card ending in 4242.` | listed | names a card |
| `Forget my Visa ending 4242.` | listed | the message holds `4242` |
| `Forget the number ending 4242.` | listed | the message holds `4242` |
| `Forget my bank card.` | listed | names a card |
| `Oublie la carte qui finit par 4242.` | listed | the message holds `4242` |
| `Vergiss meine Karte mit der Endung 4242.` | listed | the message holds `4242` |
| `Forget my gym code 4242.` | listed | the message holds `4242`; the card shows the row before anything is deleted |
| `Forget that.` | listed | names no word |
| `Forget my old phone.`, a phone account row ending `4242` | listed | `phone` is a word of the row |

The rule reads a word of the message only against the row it may keep, so a message naming the
card in other words without the digits (`Forget my Visa.`) keeps it. The safe direction of the
destructive card keeps rows, and the note names what was kept.

Beside a gym code row, `Forget my Visa ending 4242.` and `Forget the number ending 4242.` keep the
card and list the gym row under the rule above, since `visa` and `ending` are words of neither
row and `number` is a code word. That deletes the row the message did not ask for; filed as task 1157.

**Replay.** 266 forget strings, each backticked one in `docs/readings/` and the task files and
each user message of the stack's proxy log, ran through the card and the delete of the build before the
change and of the change, on the five row sets above and the phone account alone, from the storing
chat and from a new chat: 3192 cases. 294 cases from 158 strings changed, each in a new chat with
the card or the account stored alone, and none kept fewer rows. None of the 45 changed strings that
open with a forget verb names the card or the account; `Forget it but quickly.` keeps the card,
since `quickly` is no word of the row, and the note names it. The function words and forget verbs
of each language the message is read in (`FUNCTION` in `forget_languages.py`) are left out, so
`Vergiss das.` names no word and lists the card.

**The replay of the keep beside a whole value.** Its 972 changed cases hold 80 strings that open
with a forget verb. Each names another fact (`Forget my door code.`), a value no kept row holds, or
nothing, read as the newest row the chat stored, which was the gym code (`Forget what I just
said.`). None names the kept card or account, so none keeps a row the message plainly asks to
delete. The near misses that do, in the paragraph above, are not among the recorded strings.

## The card alone on the live stack: rows and the rule

Written before any draw. The build is `cortexn20-brain-s5alone`, the working tree with the change,
through the recording proxy, every card approved, `memories` emptied before each draw. The change
is in the tool and not in the prompt, so the first request of every turn is the same as on the
build before it, and a draw measures what the change does on the call the model makes.

| Row | Facts stored | Forget turn | Draws |
| --- | --- | --- | --- |
| a1 | the card, in its own chat | `Forget my gym code.`, in a new chat | 4 |
| e1 | the card, in its own chat | `Forget the card ending in 4242.`, in a new chat | 4 |
| j1 | the card, in one chat | `Forget what I just told you.`, in the same chat | 4 |

The rule: in a1 the card row is stored after every draw, and when a call text of `4242` ran, the
reply ends with `INSIDE_NOTE` naming the card. In e1 and j1 the card row is gone after every draw.
The call texts of each row are recorded, and how often a1 called `4242`, the form the change is
for, is counted apart. A null result is a draw in which no forget call ran.

## The card alone on the live stack: what was drawn

Drawn from 02:08 to 02:12 on 2026-11-12 on `cortexn20-brain-s5alone`, proxy log lines 587 to 656.
The SM clock read 0.57 of its maximum between draws.

| Row | Call texts in the forget turn | Rows listed | Row stored after | Pass |
| --- | --- | --- | --- | --- |
| a1 | `gym code`, 4 of 4, which matched no row | none | the card, 4 of 4 | 4 of 4 |
| e1 | `4242`, 3 of 4; `4111 1111 1111 4242`, 1 of 4 | the card | none, 4 of 4 | 4 of 4 |
| j1 | `4111 1111 1111 4242`, 4 of 4 | the card | none, 4 of 4 | 4 of 4 |

Every item of the rule holds, and a forget call ran in all 12 draws. The form the change is for, a
call text of `4242` for `Forget my gym code.`, occurred in none of the 4 a1 draws, so the note item
was not reached and the unit rows are its evidence. In e1 the call text `4242` listed the card in
3 draws, since the message names a card. Scripts `live.sh` and `calls.py` and log `draws.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/d2003893-7ebe-4ec3-ad1c-e92980017fd3/scratchpad/slot5/`.
