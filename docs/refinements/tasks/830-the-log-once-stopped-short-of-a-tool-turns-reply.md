# The log stopped short of a tool turn's reply or card

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)
**Verified:** 2026-10-10

On the Linux shell, with the page that has the fix closed by
[R-819](819-the-conversation-stopped-following-the-replies-of-one-chat.md), the second turn of a
chat (search, then read a message) ended with the question at the log's end and the reply below
it, while nobody scrolled; the panel had grown to its full height during that turn. The same two
questions in a fresh chat were followed to the end, as was every other turn whose end was captured
([readings](../../readings/overlay-email-flows.md#following)). A second chat repeated it: its second
turn, a send request, ended with the tool chips at the log's end and the confirmation card below
them, while nobody scrolled and the panel was already at its full height, so the person had to
scroll to reach Approve.

## What to do

Run the page with the scroll line R-819 used, read which event turned following off, and decide
which path that rule does not cover: the panel's growth, or a card added below the chips.

## History

- 2026-10-10: filed from the email flows on the Linux shell; seen in two chats.
