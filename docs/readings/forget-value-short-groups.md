# Readings: a forget of a value written in short groups

The forget card finds the other rows holding a whole value of a match with
`MemoryStore.find_value`, which compares the value's letters and digits with each row's text after
removing spaces, dots, slashes and hyphens, so a row writing `0151 2345 6789` as `015 123 456 789`
is listed ([R-1042](../refinements/tasks/1042-a-forget-misses-a-value-written-in-groups-under-four.md)).
These draws check the neighbouring flows of that change on the real model: the card's listed rows
against the stored rows.

## Rows

Each draw starts with no row of its flow, sends each seed in its own chat, and approves every card.
The stack brain is built from the working tree with the change, on the `cortexn18` stack with gemma
12B and no deep tier. Two draws of each flow, capped at 15 minutes of model time.

| Flow | Seeds | Forget turn |
| --- | --- | --- |
| v, a value named alone | `Remember that my phone number is 0151 2345 6789.`, `My bank writes my phone as 015 123 456 789. Remember that too.`, `Remember that Anna's phone is 015 123 456 999.` | `Forget 0151 2345 6789.` in a new chat |
| j, forget what was just said | `Remember that my phone number is 0151 2345 6789.`, `Remember that my phone account is 015 123 456 7890.`, `My phone is 015 123 456 789, remember it.` | `Forget what I just said.` in the last seed's chat |
| k, a keep clause | the three seeds of flow v | `Forget my phone number but keep Anna's phone.` in a new chat |

A draw passes when the card lists every row holding the person's number that the message asks to
delete, and no row holding Anna's number or the longer account number.

## The draws, 2026-11-10

03:01 to 03:06, 24 turns, SM clock 0.57 to 0.68 of `clocks.max.sm`.

| Flow | Call text | Card lists | Rows left | Pass |
| --- | --- | --- | --- | --- |
| v, both draws | `0151 2345 6789` | the seed as written, then the `015 123 456 789` row under "Listed because they also hold" | Anna's | 2 of 2 |
| k, both draws | `my phone number` | the same two rows | Anna's | 2 of 2 |
| j, both draws | `015 123 456 789` | the last seed and the `015 123 456 7890` account row; the `0151 2345 6789` row under the kept line | the `0151 2345 6789` row | 0 of 2 |

In flow j the account row is a text match of `find_text`, which finds `015 123 456 789` inside
`015 123 456 7890`, so the card deleted a row holding another number. The value search did not
list it: its whole value filter drops a longer value. The row a value search found, `0151 2345
6789`, was kept by the unnamed reader, and the reply's numbers left note said a number is still
stored, which is correct. The text match inside a longer value is task 1113.

Driver `draw.sh <flow> <draw>`, records `rows.jsonl` and logs `draw-v1.log` to `draw-k2.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot5/`.
