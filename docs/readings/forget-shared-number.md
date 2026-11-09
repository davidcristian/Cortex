# Readings: a forget that reaches a second fact through its number

What the cortex does after a `forget_memories` delete whose result says other rows still hold a
number a deleted row held. Flow n1 of [the corrections flows](overlay-corrections-flows.md) saw it
forget that number in the same turn, unasked, and so delete a second fact. The tool is
[ADR-0008](../adr/ADR-0008-memory-v1.md)'s; the closing note that tells the person the number
remains is `NUMBERS_LEFT_NOTE` in `numbers_left_claim.py`.

## The rig

**2026-11-08**, the `cortexn16` GPU stack: the resident cortex (gemma-4-12B) at a context of
16,384 tokens, no deep tier, memory on pgvector with the default `global` scope. Two seed turns,
`Remember that my gym locker number is 5521.` and `Remember that the shed padlock code is also
5521.`, ran once in their own chats; the driver copied their two rows into a template table and,
before each draw, put a fresh copy of both rows back under new ids. Each draw is one turn in a new
chat, `Forget my gym locker number.`, with every card approved. After it the driver read which of
the two rows remain and the cards the turn showed. Driver and records: `draw.sh`, `base.log`,
`fixed.log`, `*.jsonl` and `req-*.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot17/`.

## Rows and rule

Written before the first draw.

| Build | Draws | What it is |
| --- | --- | --- |
| base | 8 | the stack brain, built from `f3e6d7fb3`: the result after the first delete ends "a forget of the number itself would remove them" |
| fixed | 8 | a second brain through the recording proxy, built from the working tree: a later `forget_memories` call in the turn whose text holds a value the message does not hold, after a delete that left rows holding a deleted row's number, is refused once, and the rows are kept |

Counted per draw, on both builds: the **form** (a second `forget_memories` call naming 5521, read
from the second card on base and from the refusal in the proxy's requests on fixed), whether the
**padlock row** remains, and whether the reply says the padlock code or the number was forgotten.

**Rule.** The refusal ships when, on fixed, the padlock row remains in every draw whose first call
deletes the gym row alone, and every such draw with the form shows the refusal in its requests.
The form's count is recorded on both builds and does not decide, so a form that is rare on fixed
does not stop the fix. A fixed draw that retries the value after the refusal and deletes the row
fails the rule. A draw whose first call is the value itself is counted apart: its first request is
the same on both builds, so the change cannot reach it; this item was set apart after the base
rows and before the fixed ones. Unit tests decide the other side: a forget
the person asked for by value, in English, French, German, Spanish and Romanian, is never refused.

## Results

| Build | Draws | First call `gym locker number`, then `5521` unasked | First call `5521`, card lists both rows | Padlock row deleted | Reply names the padlock |
| --- | --- | --- | --- | --- | --- |
| base | 8 | 6 | 2 | 8 | 0 |
| fixed | 8 | 4 of 5 gym-first draws, each refused | 3 | 3, all value-first | 0 |

On base every draw deleted the padlock row with its card approved, and every reply said only "I've
forgotten your gym locker number." On fixed the padlock row remained in all 5 draws whose first
call was `gym locker number`; the 4 that then called `5521` each read the refusal and made no
retry, and all 5 replies ended with `NUMBERS_LEFT_NOTE`. The rule passes, so the refusal ships.
The 3 value-first draws deleted both rows through one card that listed both, and the reply named
only the gym locker; that form is drawn
[below](#a-first-call-by-value-that-lists-another-fact-rows-and-rule-2026-11-09).
The SM clock read 0.43 to 0.63 of its maximum (`clocks.sm` over `clocks.max.sm`) across both builds.

## A first call by value that lists another fact: rows and rule, 2026-11-09

The rig above on the `cortexn17` stack. The two seed turns ran once on the stack brain built from
`c4e83dea1`, whose replies were `I've noted that your gym locker number is 5521.` and `I've noted
that the shed padlock code is 5521.`. Driver and records: `draw.sh`, `base.log`, `fixed.log` and
`*.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot3/`.

Written before the first draw.

| Build | Draws | What it is |
| --- | --- | --- |
| base | 8 | the stack brain, built from `c4e83dea1`, which has the refusal of a later value forget |
| fixed | 8 | a second brain through the recording proxy, built from the working tree: when the call's text holds a value the person's message lacks, each matched row whose own request holds that value and that holds no word of the message is listed apart on the card and kept |

Counted per draw, on both builds: the **form** (the first call's text is `5521`), whether the
**padlock row** and the **gym row** remain, and the reply.

**Rule.** The change ships when, on fixed, every draw showing the form keeps the padlock row and
deletes the gym row, and no draw deletes the padlock row. The form's count is recorded on both
builds and does not decide; if no fixed draw shows it in 8, fixed is drawn until two do, within a
12 minute cap, and with none the change does not ship. A draw whose first call is a label reaches
the same first request on both builds, so its rows are counted but decide only the last item. Unit
tests decide the restatement side: each value first draw recorded in
[forget-value-repeats.md](forget-value-repeats.md) (fr2, yr1, frv1 to frv3, yrv1, en-r1, en-r2 and
pp1 to pp3) still deletes every row it deleted, since a recall row holds the value only in its
reply and each fact row holds a word of its message.

## The draws of both builds, 2026-11-09

The base draws ran on the stack brain and the fixed draws on a second brain through the proxy,
sharing the stack's model host and store, every card approved. The SM clock read 0.57 to 0.58 of
its maximum (`clocks.sm` over `clocks.max.sm`) before every draw on both builds.

| Build | Draws | First call `5521` (form) | Padlock row left | Gym row left | Later `5521` call, refused | Reply ends with `NUMBERS_LEFT_NOTE` |
| --- | --- | --- | --- | --- | --- | --- |
| base | 8 | 3 | 5, none of the 3 with the form | 0 | 5 of 5 label first draws | the 5 label first draws |
| fixed | 8 | 6 | 8 | 0 | 1 of 2 label first draws | 8 |

On base each of the 3 draws with the form deleted both rows through one card, and the replies were
`I've removed that from my memory.`, `OK. I've forgotten your gym locker number.` and `I've
forgotten that information.`. On fixed each of the 6 cards with the form listed the gym row to
delete and the padlock row under `Kept, since your message names none of their words:`, and each
reply was `I've forgotten your gym locker number.` with the note. No later call on either build
ran: every one was refused, so each held a value the message lacks. The fixed one was `5521`, and
the base audit keeps the texts as `<redacted>`. The rule
passes, so the change ships. Unit tests replay the value first draws of
[forget-value-repeats.md](forget-value-repeats.md), and each still deletes every row.
