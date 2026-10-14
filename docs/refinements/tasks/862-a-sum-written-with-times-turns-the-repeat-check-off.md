# A sum written with times turns the repeat check off

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md) decision 17
**Verified:** 2026-10-14

`RepeatWatch` needs one copy more than the largest count the message asks for, and reads a count as
any number before `times` or `copies`. A message that multiplies matches too: "What is 365 times
24?" makes the watch need 366 back to back copies, and "how much is 1000000 times 3" needs a
million. A reply loop on such a turn then runs to the context limit, which is what the check was
added to stop. The rule that chose this reading
([requested repeats](../../readings/reply-loop-requests.md#the-sixth-rule)) drew only messages
that ask for copies, so no row covered a sum.

Reproduction: `RepeatWatch("What is 365 times 24?").feed(line * 20)` returns `False` for any line
of 20 or more characters the message lacks; with the message "What is 365 by 24?" it returns
`True` at the third copy.

## What to do

Write a rule before changing the reading, for example a count read only when `times` or `copies`
ends the clause or follows a verb of writing, or a ceiling on the count, and draw the sixth rule's
request rows again beside a message that multiplies.

## History

- 2026-10-14: filed by the closing audit of the requested count reading.
