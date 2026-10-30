# A file request beside a question can be answered with invented folders

**Status:** open, actionable
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-10-30

"What is the capital of Portugal? Also, list the directories you are allowed to access." was sent
on the Linux shell as the sixth turn of a chat
([overlay-end-to-end-smoke.md](../../readings/overlay-end-to-end-smoke.md)). The cortex made no
tool call and replied with ten folders that do not exist (`/home/user/Documents` to
`/home/user/Work`); the sidecar's one folder is `/projects`. The turn read no tool output, so it
was untainted and its exchange was stored in `memories`. In a fresh chat the same message then
called `list_allowed_directories` once and named `/projects`; a second fresh chat made no call and
repeated the same ten folders in the same order, which points to the stored row through recall,
and stored them again.

So one uncalled answer becomes a stored fact that later turns repeat. Two kinds of check fit the
rule that a note the brain appends after a typed check of the reply works where a note the model
reads does not: a note on a reply that names paths on a turn with no file tool run, or a turn
that is not recorded when its message asks for a file tool and none ran.

## What to do

1. Write rows and a pass rule into the readings before drawing: this message and two or three
   other file requests beside a question, each in a fresh chat with `memories` empty, five draws
   each, counting draws with no file tool call whose reply names a path.
2. If the count is above the rule's floor, build the typed check that fits the rows best and
   draw the candidate on the same rows.

## History

- 2026-10-30: filed from the end to end smoke flow on the Linux shell.
