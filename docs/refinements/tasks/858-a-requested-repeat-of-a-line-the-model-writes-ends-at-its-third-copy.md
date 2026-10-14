# A requested repeat of a line the model writes ends at its third copy

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)
**Verified:** 2026-10-14

`RepeatWatch` ends a reply at the third back to back copy of a block holding a line of at least 20
characters that the person's message does not hold. A request to repeat a line the model makes up
itself has that shape, so it is cut as a loop: the person asked for the repetition, the reply
ends with `REPEATED_LINE_NOTE`, and the note's advice to ask again cannot help, since the next
reply is cut the same way. The fifth rule's request rows in
[reply loop](../../readings/reply-loop.md#the-fifth-rule) all named the line in the message, or
put other lines between its copies, so none had this shape.

## Reproduce

On the overlay, in a new chat, send "Make up one sentence of advice of about ten words for a choir
singer, then write that exact sentence ten times, one per line, and nothing else." The reply shows
three copies and the note. Sending "Please write all ten lines." in the same chat gives the same
three copies and the note again. A made up line under 20 characters runs to its end. Readings:
[overlay repeat and forget flows](../../readings/overlay-repeat-and-forget-flows.md#a-requested-repeat-of-a-line-the-model-writes).

## What to do

Write a rule into [reply loop](../../readings/reply-loop.md) before drawing anything: request rows
that ask for a made up line repeated five and ten times, beside the fourth rule's looping rig
draws, and a shape that tells them apart. One candidate reads the request, not the line: a
message asking for a count of copies (`ten times`, `5 times`) raises the copy count the watch
needs above the count asked for. A shape ships only if it still stops every looping rig draw but
at most one.

## History

- 2026-10-14: filed from the overlay flows of that night, two of three turns cut (the third made
  up a line under 20 characters).
