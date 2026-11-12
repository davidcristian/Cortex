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
