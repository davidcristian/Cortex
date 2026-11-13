# A forget in words no reader reads is refused on the answer

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

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

## History

- 2026-11-13: filed by the slot that read the open forget from earlier turns, which replayed the
  recorded turn above.
