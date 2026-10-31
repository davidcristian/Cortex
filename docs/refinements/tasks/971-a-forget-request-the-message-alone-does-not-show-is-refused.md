# A forget request the message alone does not show is refused

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-31

`unasked_forget` (`unasked_tools.py`) reads only the newest message. One real turn: with `4426` and
`8426` stored, `Forget one of my codes, but ask me which one first.` got `Which one would you like me
to forget?`, and the answer `Note that I mean the locker code.` made a `forget_memories` call that was
refused. The reply said `I've processed your request to forget the locker code.`, the row stayed, and
no note showed. Run log `t3.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot7/`.

A word the list lacks has the same result: `Note that 8426 should be zapped.` is still refused, since
it has no second clause ([readings](../../readings/forget-refused-on-remember.md#the-wordings-the-reader-missed-2026-10-31)).

## What to do

1. Pass the last assistant message of the chat to the reader, and keep the tool when it asks a
   question or names forgetting. Write near-miss tests first (a plain fact after a question about
   something else keeps being refused if the replay shows that matters), and replay the recorded
   messages through the old and new readers.
2. Decide whether a refused call should tell the model the person may have asked after all: `UNASKED_MSG`
   now says they did not.

## History

- 2026-10-31: filed from the night's closing audit, with the wordings the same commit's reader change does
  not reach.
