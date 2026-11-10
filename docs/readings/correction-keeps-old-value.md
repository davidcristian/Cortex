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
held either value, while the reply said "I've updated that" with only the forget count note
(task 1110). In c3 draw 1 the turn read a directory listing, stored nothing, and the reply `I'll make
sure to remember that your sister's name is Hannah, not Anna.` got no unkept note, since
`claims_kept` does not read `I'll make sure to remember` (task 1111). In c1 draw 4 the question
`What is my bike lock code?` in a new chat called `forget_memories`, which matched nothing (task
1112). Driver `draw.sh`, records `rows.jsonl` and logs `draw-c1.log`, `draw-c2.log`, `draw-c3.log`
in `/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot4/`.
