# A request for a line again and again with no count ends at the repeat watch

**Status:** done 2026-11-05
**Area:** inference
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)

`RepeatWatch` (`repeat_watch.py`) raises its limit only for a counted request (`10 times`) and skips
a line the message holds. `Write out the shanty chorus for me, the same long line again and again, then
one closing line.` names neither, so in 2 of 2 real turns the reply stopped at the third copy with
`REPEATED_LINE_NOTE` and no closing line. Fed directly to the class, a one-line chorus three times in a
row and a table with three equal rows end the same way. A chorus with other lines between its copies,
a numbered list and a line the message holds do not. Run log `song.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot9/`.
The note is accurate, so the cost is an unfinished answer and one more message.

## What to do

Read a request for repetition with no count (`again and again`, `over and over`, `keep repeating`) in
`_asked_count` as a higher limit, with near-miss tests first, and draw the looping rows of
[the reply loop record](../../readings/reply-loop.md) so that a real loop still ends.

## History

- 2026-10-31: filed from an audit of the opening hold's change for a sentence back a second time. That
  change does not cause this: a reply of one round reaches the watch the same way before and after it.
- 2026-11-05: done. `RepeatWatch` (`repeat_watch.py`) needs 13 back to back copies when the
  message holds `again and again`, `over and over` or `keep repeating`, the most at which every
  recorded looping draw still stopped before its token limit. Near misses (`again and then`,
  `keeps repeating`, `hangover and overtime`) keep 3, asserted in `test_repeat_watch.py`. Under a
  rule written before the rows, the shanty message and two others ran to their closing line in 9 of
  9 live turns, against the note at the third copy in 9 of 9 on the start build
  ([rows](../../readings/reply-loop-requests.md#the-seventh-rule)). The rig's message holds no
  phrase, so no looping row was drawn.
