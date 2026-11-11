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
stored, which is correct.

Driver `draw.sh <flow> <draw>`, records `rows.jsonl` and logs `draw-v1.log` to `draw-k2.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot5/`.

## A text match inside a longer value, 2026-11-10

The card now keeps a text match where a letter or digit touches the call's text at an end whose
word holds a digit (`inside` in `forget_inside.py`), and lists it under `INSIDE_LINE`. A match
that also holds the call's value whole in other separators is listed with the rows holding that
value instead, never on both lines. A call whose every match is such a kept row shows no card and
returns `INSIDE_ALL`. Replayed through the old and new
rule, 2 of the 54 distinct cards recorded in the scratchpad row logs of this night and the night
before change, both the flow j cards above, each moving the account row to the kept line.

The stack brain is rebuilt from the working tree with the change. Two draws of each flow, capped at
15 minutes of model time. Each draw starts with no row of its flow and approves every card.

| Flow | Seeds | Forget turn |
| --- | --- | --- |
| j | as above | as above |
| w, a value named alone | `Remember that my phone number is 015 123 456 789.`, `Remember that my phone account is 015 123 456 7890.` | `Forget 015 123 456 789.` in a new chat |
| k, a keep clause | the two seeds of flow w, then `Remember that Anna's phone is 015 123 456 999.` | `Forget my phone number but keep Anna's phone.` in a new chat |
| o, only a longer number | the account seed of flow w | `Forget 015 123 456 789.` in a new chat |
| e, a card by its end | `Remember my card number 4242 4242 4242 4242.` | `Forget the card ending in 4242.` in a new chat |

A draw of j, w or k passes when the card lists every row holding the person's number that the
message asks to delete and no row holding the account number or Anna's, and the account row stays.
A draw of o passes when no row is deleted and the reply says nothing was forgotten or, if it says
something was, ends with the unforgotten note. A draw of e passes when the card row is deleted.

### The draws

03:20 to 03:28, 30 turns on the stack brain and 4 on a candidate built from the same tree behind
the recording proxy (flow o only, so its call texts are recorded), SM clock 0.57 to 0.72 of
`clocks.max.sm`.

| Flow | Call text | Card lists | Rows left | Pass |
| --- | --- | --- | --- | --- |
| j, both draws | `015 123 456 789` | the last seed; the `0151 2345 6789` row under the kept line and the account row under `INSIDE_LINE` | the `0151 2345 6789` row and the account row | 2 of 2 |
| w, both draws | `015 123 456 789` | the first seed; the account row under `INSIDE_LINE` | the account row | 2 of 2 |
| k, draw 1 | `015 123 456 789` | the first seed; the account row under `INSIDE_LINE` | the account row and Anna's | 1 of 1 |
| k, draw 2 | `my phone number` | the first seed | the account row and Anna's | 1 of 1 |
| o, four draws | see below | no card | the account row | 3 of 4 |
| e, both draws | `4242 4242 4242 4242` | the card row | none | 2 of 2 |

In flow o every draw made two or three calls and none deleted a row. Of the two recorded, the
first called `015 123 456 7890` at once, and the second called `015 123 456 789`, got `INSIDE_ALL`,
then called `015 123 456 7890`; the unnamed reader kept the row at each call of the longer number,
so every reply ended with `kept_note` naming it (in the first candidate draw also the account row of a stack draw run beside
it). Three replies said nothing was found or deleted; one said `I've processed your request to forget
that number.`, which the rule fails. A call naming the longer, recalled
number is [task 1115](../refinements/tasks/1115-a-forget-of-a-value-can-call-the-longer-number-recalled-beside-it.md),
and the brain note after `INSIDE_ALL` is drawn in the next section. In flow e the model
passed the whole card number, so the `4242` text itself was not drawn.

Flow b, a row holding both: `Remember that my bank account is 44170 and my PIN is 44 17.`, then
`Forget my PIN 4417.` in a new chat, passes when the card lists that row once, to delete. Two draws
at 03:57 to 04:01 beside one each of flows w, j and k, SM clock 0.57 to 0.71: draw 1 called `4417`
and the card listed the row under "Listed because they also hold 4417", draw 2 called `44 17` and
listed it as a match; 2 of 2, no row left. Flows w and k passed as above. In flow j the third seed
turn called `forget_memories` with `0151 2345 6789` and its card deleted that row, so `Forget what
I just said.` found only the account row, kept it, and its reply ended with the unforgotten note.
Record `slot8/draws.log`, under the scratchpad named below.

### The note naming a row kept inside a longer value, 2026-11-10

The brain now appends `inside_note` after the reply, naming the rows a call with no card kept
because each holds the call's text only inside a longer value, unless a later call of the turn
deleted the row or kept it as unnamed, which `kept_note` then names instead. A draw of o passes
when no row is deleted, the reply says nothing was forgotten or ends with the unforgotten note,
and a note the brain appends names the account row; j, w and k pass as above. The form the note
is for, a turn whose only call reaching the account row returns `INSIDE_ALL`, is counted apart.

04:15 to 04:21, 26 turns on the stack brain rebuilt from the working tree with the change, two
draws of each flow, SM clock 0.57 to 0.72 of `clocks.max.sm`.

| Flow | Rows left | Pass |
| --- | --- | --- |
| o | the account row; both replies said nothing was found or deleted and ended with `kept_note` naming it | 2 of 2 |
| w | the account row | 2 of 2 |
| k | the account row and Anna's | 2 of 2 |
| j | the `0151 2345 6789` row and the account row, with the numbers left note | 2 of 2 |

The form occurred in 0 of 2 flow o draws: each made two calls, and one of them kept the account
row as unnamed (`KEPT_ALL`), so `kept_note` named the row and `inside_note` named it in neither.
The reply of draw 1 also offered to forget the phrase `phone account`; such a forget shows a card
before it deletes anything.
The engine tests in `test_forget_inside_note.py` cover the form itself. In flow k, draw 2's reply
`OK. I've forgotten your phone number and kept Anna's.` ended with `UNKEPT_CLAIM_NOTE`, since no
call matched Anna's row; the forget card now also reports the rows a keep clause names
([readings](closing-note-language.md#a-keep-claim-naming-a-row-still-stored-2026-11-10)).
Record `slot9/draws.log`, under the scratchpad named below.

### A call naming a longer number than the message, 2026-11-11

The card now keeps a match when the call's text names a value the message lacks and the match
holds every value the message names only inside a longer value (`longer` in `forget_longer.py`).
The unit and engine tests in `test_forget_longer_value.py` and `test_forget_inside_note.py` cover
the form of [task 1115](../refinements/tasks/1115-a-forget-of-a-value-can-call-the-longer-number-recalled-beside-it.md)
without a draw. Flow e and flow b were written as tests before the change and pass on both builds.

Neighbouring flows, one draw each, 03:42 to 03:44 on `cortexn19-brain-s11` (the working tree with
the change), SM clock 0.57 of `clocks.max.sm`. A draw passes when every row its message asks to
delete is deleted.

| Flow | Call text | Rows left | Pass |
| --- | --- | --- | --- |
| e, a card by its end | `4242 4242 4242 4242` | none | yes |
| w, a value named alone | `015 123 456 789` | the account row | yes |
| s, `Remember that my locker code is 3141.` then `Forget what I just said.` | `locker code is 3141` | none | yes |

Record `slot11/draws.log` under the scratchpad below.

Driver `draw.sh <flow> <draw>`, candidate driver `cand-o.sh`, records `rows.jsonl` and `cand.jsonl`,
proxy log lines 47 to 63 of `stack/logs/proxy-req.jsonl`, under
`/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/` (`slot6/` and `stack/`).
The slot 11 record is under
`/tmp/claude-1000/-home-david-Files-Git-Cortex/f3217b06-cdcf-4ffa-92c2-cc5df81e7d11/scratchpad/`.
