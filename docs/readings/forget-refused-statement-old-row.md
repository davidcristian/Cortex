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
ask to forget it. It also calls the value the one the message corrects, which is false beside a
row of another fact whose words the message all holds
([open task](../refinements/tasks/1188-the-old-value-note-names-a-row-of-a-shorter-fact.md)).
The note text and its four translations are unchanged.

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
