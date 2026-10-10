# The log once stopped short of a tool turn's reply

**Status:** open, waiting for its trigger
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)
**Verified:** 2026-10-10
**Trigger:** a second turn on any shell whose log ends above its own reply while nobody scrolled,
on a page that has the following fix closed by task 819

On the Linux shell, with the page that has the fix closed by
[R-819](819-the-conversation-stopped-following-the-replies-of-one-chat.md), the second turn of a
chat (search, then read a message) ended with the question at the log's end and the reply below
it, while nobody scrolled; the panel had grown to its full height during that turn. The same two
questions in a fresh chat were followed to the end, as was every other turn whose end was captured
([readings](../../readings/overlay-email-flows.md#following)).

## What to do when it fires

Run the page with the scroll line R-819 used, read which event turned following off, and decide
whether the panel's growth is a path that rule does not cover.

## History

- 2026-10-10: filed from the email flows on the Linux shell; one sighting, not reproduced.
