# Readings: memory that changes over time, on the Linux shell

What the overlay, the recall and the memory store did when a person told the assistant a fact and
later changed it, each statement in its own chat, and then asked about it in a new chat: a fact
updated with words that mark the change, a fact contradicted with no such words, and one value
replaced twice. Earlier flows stored and recalled one fact
([file and memory flows](overlay-file-and-memory-flows.md)) or removed memories
([repeat and forget flows](overlay-repeat-and-forget-flows.md)); these give the store several
values for one fact.

## The rig

**2026-10-26**, the shared stack of that night (compose project `cortexn8`, its own volumes): the
cortex gemma-4-12B at a 16384 context on the GPU, Postgres with pgvector and the CPU embedder, the
default global memory scope and the default `judge` recall rank, with
`CORTEX_MEMORY_RECALL_AUDIT=1` so each recall logs the ids it kept. The overlay ran in the debug
Linux shell on `Xvfb`, as [the overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless)
describes, driven with `xdotool`. Every statement and every question was sent in a new chat
(`Ctrl+N`), so only memory joined them. Replies were read from the chats' Redis lists, memories
from the `memories` table, recalls from the brain's `cortex.memory.recall` lines.

**The right behaviour, written before the first row:** the answer names the newest value the person
gave. A recall that hands the turn an older value beside a newer one is recorded as such, since it
is the condition [R-087](../refinements/tasks/087-tiered-self-editing-memory.md) waits for. A
recalled memory is shown to the model as its text alone (`turn_context.py`), with no date, so
nothing but the words of the exchange tells the model which value is newer.

## A fact updated with words that mark the change

"Please remember this: my favourite colour is green.", then "An update to remember: my favourite
colour is now blue, not green any more.", then "What is my favourite colour? One word." **As
expected:** "Blue". The rank kept both exchanges, blue first and green second, so the turn was
handed the old value beside its correction, the condition R-087 waits for, and the words "now" and
"not green any more" told the model which one held.

## A fact contradicted with no such words

"Please remember this: I live in Lyon.", then "Please remember this: I live in Porto." The second
statement raised the `forget_untrusted_memories` card, whose tool removes memories derived from
untrusted content and updates nothing; its recall had handed the turn no memory. The card was left
unanswered, and the next `Ctrl+N` two minutes later declined it, so that chat stored the question
and no reply, and "Which city do I live in? One word." was answered "Lyon" from the one value
stored. Sent again in a new chat, the Porto statement was answered "OK. I've noted that you live in
Porto." with no card, and the question then recalled only that exchange and was answered "Porto".
The card on a request to remember is filed as
[R-900](../refinements/tasks/900-a-request-to-remember-a-fact-can-raise-the-forget-card.md).

## One value replaced twice

"Please remember this: my dentist appointment is on Tuesday.", then the same with Thursday (the
reply asked for the date and time rather than confirming it) and with Friday, then "Which day is my
dentist appointment? One word." **Not as expected:** "Tuesday". The three exchanges led the pool at
raw similarity 0.78 (Thursday), 0.77 (Friday) and 0.77 (Tuesday), and the `judge` rank kept only
Tuesday, so the turn was handed the oldest value alone. The rank's numbered notes and the reply's
memory list are texts with no date, so neither the rank nor the reply could tell the values apart
by age.

The replication, written before it ran, used a gym class on Monday, then Wednesday, then Saturday.
The rank kept all three, in the order Wednesday, Monday, Saturday, and the answer was "Saturday".

## Many memories

Written before it ran: ten facts about the person, each stated in its own new chat, with the first
renamed after the other nine ("My cat is called Miso", later "I renamed my cat, she is called Pip
now"), then three questions in new chats about the first, a middle and the last fact, and one
about the cat. Each answer passes when it names the fact as last stated.

Of the eleven statements, ten were answered with a confirmation. "Please remember this: my sister's
name is Ana." raised the `forget_untrusted_memories` card again, with no earlier fact about a
sister; the next `Ctrl+N` declined it, so nothing about the sister was stored, and the question
about her was answered "I don't have any information about your sister's name." The film and the
friend were answered "Alien" and "Tomas" from one kept exchange each. **Not as expected:** "What is
my cat called? One word." was answered "Miso". The rank kept both cat exchanges, the rename first
and the first statement second, so the reply named the older value with the newer one listed above
it and worded as a rename.

## Summary

| flow | values stored, oldest first | the rank kept | answer | newest named |
| --- | --- | --- | --- | --- |
| colour | green, blue | blue, green | Blue | yes |
| city | Lyon, Porto | Porto | Porto | yes |
| dentist | Tuesday, Thursday, Friday | Tuesday | Tuesday | no |
| gym | Monday, Wednesday, Saturday | Wednesday, Monday, Saturday | Saturday | yes |
| cat, among ten facts | Miso, Pip | Pip, Miso | Miso | no |

Three of five answers named the newest value. In three of five the turn was handed superseded
values beside the newest, which fires the trigger of R-087 on this stack, and one of those answers
named the superseded value; in one more the rank kept only the oldest value. Filed as
[R-899](../refinements/tasks/899-a-changed-fact-can-be-answered-with-its-older-value.md).
The forget card was raised by 2 of the 22 requests to remember in these flows.

Method: the drivers (`turn.sh`, `flowA1.sh`, `flowA2.sh`, `flowA3.sh`) are in the run's scratch
directory, not in the tree.
