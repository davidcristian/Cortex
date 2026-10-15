# A recap of a cut message describes the part it never read

**Status:** open, actionable
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-10-15

One fold reads at most `RECAP_READ_MAX` characters, and `fold_slice` cuts a longer first message
under a line saying how many characters were cut. On the Linux shell on 2026-10-15 the fold over a
60,175-character pasted log read its first 16,000 characters and wrote a recap saying the log's
status codes were "all 200", though the log ends with an error line the fold never saw
([readings](../../readings/overlay-long-and-unusual-input.md#a-pasted-log-past-the-context)).
The cut line is in the quoted transcript, and nothing in `_INSTRUCTION` tells the model what it
means.

## What to do

This is a change to what the model is asked, so it ships only on rows with a pass rule written
first. Write the rule in the readings (a recap passes when it says the message was cut and states
nothing about the unread part as fact), draw a baseline of folds over the two logs in
`measurements/overlay-long-input-2026-10-15/`, then compare two treatments: one instruction
sentence on the cut line, and a cut that keeps the message's head and tail. Pick on the rows.

## History

- 2026-10-15: filed from the after-fix flow of the bounded fold on the Linux shell.
