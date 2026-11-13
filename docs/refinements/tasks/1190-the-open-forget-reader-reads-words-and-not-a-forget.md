# The open forget reader reads words and not a forget

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

`forget_unrequested` (`forget_unrequested.py`) keeps the forget tool on an English statement of a
fact when a message of the person in the last two exchanges holds what `_CAN_RETRACT` or
`_misspells_forgetting` reads ([the reader](../../readings/forget-refusal-english-statement.md)).
That reader was written wide for the message itself, so it reads most chats as holding an open
forget. With the last reply `Got it. Anything else I can help with?`, the statement `My alarm code
is 5528.` keeps the tool after each of `Don't forget my dentist on Friday.`, `I forgot my keys.`,
`Remember to buy milk.`, `I'm not sure yet.`, `No, that's fine.`, `I used to live in Berlin.`,
`I'm at the café.`, `Can you update my calendar?` and `What did I tell you earlier?`, and the
stated fact can be lost as before the reader. The same reader misses a forget written in words it
does not list: after `Get my phone number out of there.` and the reply `Which one, work or
personal?`, the statement `My work phone is 0744 111 222.` is refused the tool. Both are
reproduced by
`/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot14/repro.py`.

## What to do

1. Write tests first from the messages above, and count how often the reader reads an open
   forget on the recorded person messages of the proxy log.
2. Read an open forget from what the earlier turn did rather than from its words: a forget call
   it made, a refusal it got, or a reply that named forgetting. Keep the tool when unsure.
3. Replay every recorded message and test string with its earlier messages through the start
   build and the new reader, and name every string whose result changes.

## History

- 2026-11-13: filed by the third audit of the night, which reproduced both forms at HEAD.
