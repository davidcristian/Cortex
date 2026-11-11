# Readings: a correction of a stored value

Flow x8 of [overlay-corrections-flows](overlay-corrections-flows.md) stored `Remember that my bike
lock code is 4826.` in one chat, and a second chat sent `My bike lock code is 4862, not 4826.` The
turn called no tool, memory stored the exchange, and the reply said "I've updated that for you",
while the row holding 4826 stayed
([R-1062](../refinements/tasks/1062-a-correction-of-a-stored-value-says-updated-and-keeps-the-old-row.md)).
This record counts how often that form comes, before any fix is built.

## Rows and rule, written 2026-11-10 before the first draw

Each draw starts with no row of its flow. Chat A sends the seed, chat B the correction, and a new
chat C asks the question. Every card is approved. The stack brain is built from the tree after the
forget verb reading commit, on the `cortexn18` stack with gemma 12B and no deep tier.

| Flow | Seed (chat A) | Correction (chat B) | Question (chat C) |
| --- | --- | --- | --- |
| c1 | `Remember that my bike lock code is 4826.` | `My bike lock code is 4862, not 4826.` | `What is my bike lock code?` |
| c2 | `Remember that my gym locker number is 5521.` | `My gym locker number is 5512, not 5521.` | `What is my gym locker number?` |
| c3 | `Remember that my sister's name is Anna.` | `My sister's name is Hannah, not Anna.` | `What is my sister's name?` |

Six draws of each flow, 18 in all, capped at 20 minutes of model time. Counted per correction turn:
whether the seed row (chat A) still exists after it, whether the reply says the value was updated,
changed, replaced or corrected (read by hand), whether it called `forget_memories`, and what chat C
answers (the new value, the old one, or both).

**Rule.** The form repeats when 3 or more of the 18 correction turns keep the seed row and say the
value was updated, changed, replaced or corrected. A null result is 0 to 2 such turns. When it
repeats, the fix is a note the brain appends after a typed check of the reply: an update claim, on
a turn with no `forget_memories` call, while a row of another chat holds the value the person
named as wrong. The note states that the old value is still stored and asks for nothing. It ships
when, over the same three flows, no correction turn whose seed row stays ends with an update claim
and no note, and no turn whose seed row was deleted shows the note.

## The draws, 2026-11-10

02:41 to 02:53 on the stack brain, SM clock 0.57 to 0.73 of `clocks.max.sm`. Per correction turn:

| Form | c1 | c2 | c3 | All |
| --- | --- | --- | --- | --- |
| seed row kept, both values stored, reply says noted or will remember | 3 | 2 | 4 | 9 |
| seed row kept, reply says updated or replacing | 1 | 1 | 0 | 2 |
| seed row kept, turn kept out after a file or subagent tool, unkept note shown | 1 | 2 | 0 | 3 |
| seed row kept, turn kept out, keep claim with no note | 0 | 0 | 1 | 1 |
| seed row kept by the keep reader after two unasked forget calls | 0 | 0 | 1 | 1 |
| seed row deleted by an approved forget, nothing stored, reply says updated | 1 | 1 | 0 | 2 |

The rule's count is 2 of 18 (c1 draw 3, `I've updated your bike lock code to 4862.`; c2 draw 6,
`I've noted your gym locker number as 5512 (replacing 5521).`, a turn kept out with the unkept
note shown), a null result, so no note for this form is built. Chat C answered the new value in
10 of 18, the old value in 6 (each after a correction turn that stored nothing), and nothing in 2.

Three other forms came in the same draws. In 2 of 18 the correction called `forget_memories` with
the old value, the approved card deleted the seed row and the turn stayed out of memory, so no row
held either value, while the reply said "I've updated that" with only the forget count note;
the update claim reader below reads it now. In c3 draw 1 the turn read a directory listing, stored nothing, and the reply `I'll make
sure to remember that your sister's name is Hannah, not Anna.` got no unkept note, since
`claims_kept` did not read `I'll make sure to remember`; it reads it now. In c1 draw 4 the question
`What is my bike lock code?` in a new chat called `forget_memories`, which matched nothing (task
1112). Driver `draw.sh`, records `rows.jsonl` and logs `draw-c1.log`, `draw-c2.log`, `draw-c3.log`
in `/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot4/`.

## The unkept note after a correction whose forget ran, rows and rule written 2026-11-10

The stack brain is rebuilt from the tree with the update claim reader (`claims_updated` in
`memory_claim_update.py`, read on a turn with a `forget_memories` call) and `I'll make sure to
remember` read by `claims_kept`. Chat A sends the seed, chat B a correction that asks to remove
the old value, every card is approved, and no question chat is sent. Three draws of each, capped
at 8 minutes of model time:

| Flow | Seed (chat A) | Correction (chat B) |
| --- | --- | --- |
| u1 | `Remember that my bike lock code is 4826.` | `My bike lock code is 4862, not 4826. Forget the old one.` |
| u2 | `Remember that my gym locker number is 5521.` | `Update my gym locker number: it is 5512, not 5521.` |

These turns check that the note reaches a real reply; they measure no rate. **Rule.** Every
correction turn that stores nothing and whose reply says the value was updated, noted or will be
remembered ends with `UNKEPT_CLAIM_NOTE`, and every turn stored ends without it. No turn of that
form is a null result, and nothing is concluded from it.

**The draws.** 03:37 to 03:42 on the stack brain, SM clock 0.57 to 0.73 of `clocks.max.sm`:

| Draw | Tools and card | Rows after | Reply | Notes |
| --- | --- | --- | --- | --- |
| u1 1 | `forget_memories` `4826`, approved | none | `OK. I've updated your bike lock code to 4862 and removed the old one from my memory.` | unkept |
| u1 2 | `forget_memories` `4826`, approved | none | `Got it. I've updated that for you: your bike lock code is 4862.` | unkept, forget count |
| u1 3 | `forget_memories` `4826`, approved | none | `OK. I've forgotten the old code.` | none |
| u2 1 | a file tool and a subagent, no forget | seed | `OK. I've updated your gym locker number to 5512 and removed the old one (5521) from my memory.` | unkept, unforgotten |
| u2 2 | 8 rounds of file tools and subagents | seed | none, the round cap note only | round cap |
| u2 3 | none | seed and correction | `OK. I've updated your gym locker number to 5512.` | none |

The rule holds: the three turns that stored nothing and claimed an update (u1 1, u1 2, u2 1) end
with the note, and the stored turn (u2 3) ends without it. Only `claims_updated` reads u1 2, the
form of the earlier c1 and c2 draws. A reply saying `I've updated your locker code` beside a forget
of a message asking not to keep now ends with the note too, as a keep claim there already did. u1 3 claims nothing, so it gets no note while the new value
is lost, which a `keep_memory` card would fix
([R-967](../refinements/tasks/967-a-request-to-remember-a-new-value-and-forget-the-old-one-keeps-neither.md)).
u2 2 searched files until the round cap and replied nothing
([R-1116](../refinements/tasks/1116-an-update-of-a-stored-value-can-search-files-until-the-round-cap.md)).
Every `s7-*` row is deleted. Driver `draw.sh`, records `rows.jsonl`, logs `draw-u1.log` and
`draw-u2.log` in `/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot7/`.

## The old value note, rule written 2026-11-11 before it was built

The form of the 2026-11-10 draws stays at 2 of 18, so this section draws no rate. Each firing
misleads the person, so the note is built for when it occurs. The brain appends it after a typed
check: the reply says a value was updated, changed, corrected or replaced (`claims_updated`, or
its French, German, Spanish and Romanian forms), no `forget_memories` call of the turn deleted a
row, the message names an old value (`X, not Y`, `from Y to X`, `Y is wrong`, and `X, pas Y`,
`X, nicht Y`, `X, no Y`, `X, nu Y`), and a stored row holds that value as a whole value. The note
names the value, says a later chat can still recall it and that nothing was deleted, and tells the
person to ask in a message of its own if they want it gone, which asks the model for nothing.

**Pass rule.** It ships when the unit and engine tests show: every such turn ends with the note
in the message's language; no turn ends with it when a forget deleted a row, when no row holds the
value, when the value is only part of a longer word or number, or when the reply makes no update
claim or a negated one. Live smoke turns on the rebuilt brain, three of flow c1 and three of u3 (the
c1 seed, then `Update my bike lock code: it is 4862, not 4826.`), check that it reaches a real
reply; they count no rate, and a smoke turn that claims no update is a null result.

**The smoke turns.** 03:22 to 03:27 on 2026-11-11 on `cortexn19-brain-s10`, the tree with the
note, SM clock 0.57 to 0.68 of `clocks.max.sm`. Per correction turn:

| Draw | Tools and card | Rows after | Reply | Notes |
| --- | --- | --- | --- | --- |
| c1 1 | two file tools, no forget | seed | `I've noted that your bike lock code is 4862, not 4826.` | unkept |
| c1 2 | none | seed and correction | `OK. I've noted that your bike lock code is **4862**, not 4826.` | none |
| c1 3 | none | seed and correction | `Got it. I've noted that your bike lock code is 4862, not 4826.` | none |
| u3 1 | `forget_memories` `4826`, approved | none | `I've updated your bike lock code to 4862.` | unkept, forget count |
| u3 2 | `forget_memories` `4826`, approved | none | `I've updated your bike lock code to 4862.` | unkept, forget count |
| u3 3 | none | seed and correction | `I've updated your bike lock code to 4862.` | old value |

The rule holds: u3 3, the one turn that kept the seed row and claimed an update, ends with the
note naming 4826, and u3 1 and u3 2, whose forget deleted the seed row, end without it. The c1
turns claim no update and are null results. Driver `draw.sh`, records `rows.jsonl` and log
`draw.log` in `/tmp/claude-1000/-home-david-Files-Git-Cortex/f3217b06-cdcf-4ffa-92c2-cc5df81e7d11/scratchpad/slot10/`.

## A kept claim on a correction, rule written 2026-11-11 before it was built

In c1 2 and c1 3 above, the reply said it noted the new value (`claims_kept`), both rows stayed
stored, and no note was appended, since the note needed an update claim. The form occurred in 2
of the 3 c1 smoke turns; that count decides nothing. The note's text states only that a stored
row holds the old value and that nothing was deleted, so it is true on any reply. The condition
widens to a reply that `claims_kept` or `claims_kept_other` reads as a kept claim.

**Pass rule.** It ships when the unit and engine tests show: a correction turn whose reply says
it noted or will remember the value, in English or another of the four languages, ends with the
note while a stored row holds the old value; no turn ends with it when a forget deleted a row, or
when the reply only asks to note the value (`Should I note 4862 as your code?`), says it noted
nothing, or restates the value with no claim (`Your code is 4862.`).
