# A forget in words no reader reads is refused on the answer

**Status:** declined 2026-11-27
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`forget_open` (`forget_open.py`) reads an open forget from what the last two exchanges did: a
forget call that ran, a reply naming forgetting, or a person's message `asks_to_forget` reads. A
request to forget in other words that the model answers with a clarifying question naming none of
them opens nothing, so the English statement that answers it is refused the forget tool. The
night's proxy log holds one such turn: `Cancel the code I gave you.`, then a reply asking `Could
you please clarify which code you are referring to, or let me know if there's something specific
you'd like me to ignore or stop using?`, then `My alarm code is 5528.`, refused
([readings](../../readings/forget-open-from-earlier-turns.md)). `Get my phone number out of there.`
answered by `Which one, work or personal?` reads the same way. The person's forget is not run, and
the reply says nothing about it.

## What to do

1. Count the form on the live stack: cancel flows in other words (`Cancel`, `Get it out of
   there`, `Scrap the code`), with how often the first reply runs a call, names forgetting or
   does neither.
2. Do not widen a word list. When the form occurs, prefer a note the brain appends to the reply
   of a turn whose forget call was refused while the last reply asked a question, written to be
   true on every turn it reaches, over a wider reader.

## The count of step 1

Written before its first draw. Three messages, 8 draws each, every card approved, each draw one
chat of two turns with the old value seeded first: `Cancel the code I gave you.` then `My alarm
code is 5528.` over the row `Remember that my alarm code is 4242.`; `Get my phone number out of
there.` then `My phone number is 0721 555 9876.` over `Remember that my phone number is 0721 555
4242.`; `Scrap the code.` then `My alarm code is 5528.` over the alarm row. Counted per draw: on the
first turn, forget calls written and refused, a forget run, a reply that asks a question, a reply
naming forgetting (`names_forgetting`), and neither; on the second, forget calls written and
refused; at the end, the old row kept or deleted and the new value stored.

**Rule.** The form occurs on a message when, in 2 or more of its 8 draws, the first turn runs no
forget and its reply names no forgetting, and the second turn's forget call is refused with the old
row still stored. Step 2 is then started on that message; on fewer than 2 it is not.

## History

- 2026-11-13: filed by the slot that read the open forget from earlier turns, which replayed the
  recorded turn above.
- 2026-11-26: meets the bar of the freeze of the forget message readers ([ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md) decision 7): it rests on a recorded live turn, `Cancel the code I gave you.` then `My alarm code is 5528.`, refused, and its remedy is a note the brain appends, not a wider word list.
- 2026-11-27: declined on the count of step 1, drawn live with the old value seeded: the form came
  in 1 of 24 draws (`Cancel the code I gave you.`, 1 of 8; the phone and scrap messages, 0 of 8),
  under the rule's bar of 2 on every message, and that reply already ended with the old value note
  saying a remembered exchange still holds the code
  ([readings](../../readings/forget-open-from-earlier-turns.md#a-forget-in-other-words-then-a-new-value-2026-11-27)).
  The new value was not stored in 12 of the draws; the rule that stores it is in the
  [readings](../../readings/forget-open-from-earlier-turns.md#a-statement-after-a-forget-stored-2026-11-27).
