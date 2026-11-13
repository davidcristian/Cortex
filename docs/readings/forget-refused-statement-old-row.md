# Readings: the old row beside a refused statement of a fact

How `hold_old_value` (`memory_old_value.py`) reads a statement that gives a stored fact another
value without naming the old one. The note is the old value note of
[correction-keeps-old-value.md](correction-keeps-old-value.md); the refusal of the forget tool on
such a statement is in [forget-refusal-english-statement.md](forget-refusal-english-statement.md).

## What the reader does, 2026-11-13

`forget_unrequested` refuses the forget tool on `My alarm code is now 5528.`, `My birthday is
actually 12 May.`, `My new number is 0721 555 019.`, `My current number is 0721 555 019.` and `My
phone number was 0721 555 019.`. Beside a stored `My alarm code is 4826.` the older row then
stayed with no note, since `corrected_values` reads only a message naming the old value.

`_replaced` now reads a message that is one English statement of a fact (`FACT_VALUE` in
`fact_statement.py`, the shape of `STATEMENT` with the fact's words and the value as groups) and
holds no negation word of `NOT` (`forget_clauses.py`). It searches the rows the chat can recall
for the fact's words and each shorter ending of them (`alarm code`, then `code`), and takes the
first row whose user line states a fact in the same shape with the same possessive, every word of
which the message names, with a value the message does not hold and that does not hold the
message's value. Both values must hold a digit, since `My sister is vegan.` beside `my sister is
Ana` gives another detail of the fact rather than a new value of it. The old value note then names
that value, whatever the reply says, unless a forget of the turn deleted a row.
The note says a remembered exchange still holds the value, nothing was deleted and the person can
ask to forget it. It also calls the value the one the message corrects, which was false beside a
row of another fact whose words the message all holds, until the
[change of 2026-11-14](#equal-fact-words-and-the-present-tense-2026-11-14). The note text and its
four translations are unchanged.

No note: `My code is 5528.` beside the alarm code (the row names `alarm`), `My number is 0721 555
019.` beside `My phone number is 0721 555 018.`, `My code is 4862 not 4826.` (a negation), `My
card is 4242.` beside a card ending in `4242`, a question, a row whose value is the stated one,
`Her phone is 0721 555 019.` beside `my phone is 0744 111 222`, and a value with no digit on
either side (`My phone is broken.`, `My kids are 5 and 7.` beside `my kids are Ana and Ion`).
The tests are `test_memory_old_fact.py`; one row of `test_memory_old_value.py`, `My bike lock code
is 4862.` beside `my bike lock code is 4826`, moved there, since it now gets the note.

## Replay through HEAD and the change

Taken 2026-11-13 at HEAD `018c2367c` and the working tree, over 33,191 distinct strings (the string
literals of every test and doc, the night's proxy log and the audit's probe messages) as the
message, each over four row sets (ten facts together, the alarm code alone, two phone rows, a
name and a city) and two replies (`Got it.` and `I've updated that for you.`).

| Cases | Changed | Note added | Note lost | Other value |
| --- | --- | --- | --- | --- |
| 265,528 | 24 from 7 strings | 24 | 0 | 0 |

Each added note names a row stating the same fact: `4826` for `My alarm code is now 5528.` and
`My bike lock code is 4862.`, `0721 555 018` for four test strings `My number is 1063.` and the
like, and `4111 1111 1111 4242` for `my card is 4242 4242`. The scripts `replay2.py` and
`diff2.py` and the logs `old2.jsonl` and `new2.jsonl` are in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot11/`.

## The store turn on the live stack: rows and the rule

Set in the draw script before any draw. The build is the working tree with the change, run as
`cortexn21-brain-s11fact` (memory tools only, like the stack brain), every card approved, every
row deleted before each draw, and the fact stored in a chat of its own.

| Row | Fact stored | Statement | Draws |
| --- | --- | --- | --- |
| a | `My alarm code is 4826.` | `My alarm code is now 5528.`, a new chat | 2 |
| s | `My alarm code is 4826.` | `My alarm code is now 5528.`, the same chat | 2 |
| b | `My alarm code is 4826.` | `My bike code is 5528.`, a new chat | 2 |

The rule: in a and s, every reply after which the `4826` row is still stored ends with the old
value note naming `4826`; in b, no reply has that note. How often a forget call runs is counted
apart and fails no item.

## The store turn on the live stack: what was drawn

Drawn from 06:29 to 06:30 on 2026-11-13, proxy log lines 851 to 874. The SM clock read 0.58, 0.59
and 0.58 of its maximum before, between and after the draws.

| Row | Replies ending with the note naming `4826` | `4826` row stored after | Forget calls |
| --- | --- | --- | --- |
| a | 2 of 2 | 2 of 2 | 0 |
| s | 2 of 2 | 2 of 2 | 0 |
| b | 0 of 2 | 2 of 2 | 0 |

Every item of the rule holds. In one s draw the reply said it had removed the previous code, and
the claim note and the old value note both followed it. The script `draw2.sh` and the logs
`draw2.log` and `draws2.jsonl` are in the slot directory above.

## Equal fact words and the present tense, 2026-11-14

The reader above took a row whose fact words were all among the message's own, so `My work phone
is 0721 555 019.` and `My sister's phone is 0721 555 019.` named `my phone is 0744 111 222`, `My
gym code is 4242.` named `my code is 1234`, and a message stating a past value (`My old phone
number was 0744 111 222.`, `My previous address was 12 Elm Street.`) named the current value as
the one it corrects. The note then offered to forget a row the person did not mean.

`_replaced` now takes a row only when the message's fact words are the row's, plus at most the
words of change `new`, `current` and `actual` (`_CHANGE_WORDS`), and `FACT_VALUE` reads only `is`
and `are`, so neither a message nor a row stating a past value counts. `now` is not a word of
change: after the copula it is part of the value, and after the fact words (`my number now is`)
the search, which looks for each ending of the fact words, finds no row. The search is unchanged,
so the reader names no row it did not name before. A value with no digit still counts on neither
side, a capitalized name or an email address included: `My sister is Maria.` beside `my sister is
Ana` has equal fact words and names a second sister, so equal words do not make a name a new value
of the same fact. The tests are the near-miss rows of `test_memory_old_fact.py`.

### Replay through HEAD and the change

Taken 2026-11-14 at HEAD `d1804ae28` and the working tree, over 188,929 distinct strings: every
string literal of the tracked Python files, every line and backticked span of the tracked markdown,
the 79 user messages of the night's proxy log, and each sentence and line of all of them. Each
string was the message over four row sets (twelve facts together, the alarm code alone, two phone
rows, a name and a city) and two replies (`Got it.` and `I've updated that for you.`) through
`hold_old_value`; each of the 81 strings that is a statement was also the message beside each of
the 448 strings stating a fact with a digit, stored as a row of its own, through `_replaced`.

| Cases | Changed | Note added | Note lost | Other value |
| --- | --- | --- | --- | --- |
| 1,547,720 | 903 from 25 strings | 0 | 903 | 0 |

| Lost because | Cases | Strings | Examples |
| --- | --- | --- | --- |
| A word naming another fact | 552 | 15 | `My work phone`, `My sister's phone`, `My phone at work` beside `my phone`; `My gym code`, `My locker code`, `My alarm code` beside `my code` |
| The message states a past value | 254 | 5 | `My old locker code was 1234.`, `My phone number was 0744 111 222.`, `My previous address was 12 Elm Street.` |
| `old` marks the stated value | 53 | 1 | `My old phone number is 0744 111 222.` beside `my phone number` |
| More words for the same fact | 39 | 4 | `My phone number is 0744 111 222.` and `My new phone number is 0721 555 019.` beside `my number`; `Our wedding anniversary is on 20 May.` beside `our anniversary` |
| The row states a past value | 5 | 4 | a row `My phone number was 0721 555 019.` |

The fourth line is the cost: the reader cannot tell `phone number` beside `number` from `work
phone` beside `phone`, so it names neither. On the four fixed row sets the 32 lost cases come from
11 of the strings above, and `My new number`, `My current number`, `My alarm code is now 5528.` and
`My bike lock code is 4862.` name the same rows as before. The scripts `replay.py`, `classify.py`
and `classes.py`, and the logs `replay.log` and `replay.jsonl`, are in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/11450320-079c-401d-9f26-43a763a369b6/scratchpad/slot2/`.

### Turns on the live stack

The rule, set in `draw-rule.md` in the slot directory before any draw: every row deleted before
each draw, the fact stored in a chat of its own and the statement sent in a new chat, every card
approved. In w, on the build with the change (`cortexn22-brain-s2fact`), no reply ends with the
old value note naming `0744 111 222`; in n, on the same build, every reply after which the `0721
555 018` row is still stored ends with the note naming it. w0 runs w on the build before the
change (`cortexn22-brain-s1fix`) and fails no item.

| Row | Fact stored | Statement | Replies with the note | Old row stored after |
| --- | --- | --- | --- | --- |
| w | `my phone is 0744 111 222` | `My work phone is 0721 555 019.` | 0 of 2 | 2 of 2 |
| n | `my number is 0721 555 018` | `My new number is 0721 555 019.` | 2 of 2 | 2 of 2 |
| w0 | as w | as w | 1 of 1 | 1 of 1 |

Drawn from 00:09 to 00:12 on 2026-11-14, proxy log lines 135 to 165, no forget call. The SM clock
read 0.58 of its maximum before and after. Every item of the rule holds. One w reply
said it also had the other phone number on file, which is true. The script `draw.sh` and the logs
`draw.log` and `draws.jsonl` are in the slot directory above.
