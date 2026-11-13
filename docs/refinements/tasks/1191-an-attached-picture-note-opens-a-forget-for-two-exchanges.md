# An attached picture note opens a forget for two exchanges

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

The turn engine stores a person's message with `attachment_note` (`attachments.py`) appended:
`(Attached to this message and not kept: image/png 640x480.)`. `_earlier_asks` (`tool_loop.py`)
hands that stored text to `forget_unrequested` as the person's own message, and `_CAN_RETRACT`
reads its `not`. So for two exchanges after any picture an English statement of a fact keeps the
forget tool: the chain `Look at this.` with a picture, `Nice photo! How can I help with it?`, then
`My alarm code is 5528.` runs the forget call, and the same chain with no picture refuses it. On
a handoff the turn's own query also holds the note (`_user_query` in `brain_phase.py`). Reproduced
by `/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot14/repro.py`.

## What to do

1. Write a turn test first: the chain above refuses the forget with the picture as without it.
2. Read the person's text without the attachment note, as `model_text` does for the brain's
   notes on a reply, in `_earlier_asks` and in the handoff's query.
3. Replay the recorded draws that attach a picture, if any, and name every changed result.

## History

- 2026-11-13: filed by the third audit of the night. It refuses more, so it was not fixed there.
