# The cortex describes a file whose read did not fit

**Status:** open, actionable
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-10-28

On 2026-10-28, on the `cortexn9` stack, "Read /projects/bravo.log and /projects/charlie.log with
read_text_file in one step and summarize what went wrong in each." made one `read_multiple_files`
call for both files and then two `read_text_file` calls. The reply summarized `charlie.log` as a
fatal error with a system shutdown on batch 00001, a disk full, a deadlock, a timeout and a
denied permission. None of these words is in `charlie.log`, whose lines are all of the
`processed`, `flushed`, `retried` and `queued` kind.

Inferred from the room's rule, not observed (the brain's log was lost when it was recreated): the
first result held both files, over 47,500 characters, so its first 6,000 kept only the start of
`bravo.log`, and the room was then spent, so both `read_text_file` results were `NO_ROOM_NOTE`,
which already says to answer from what was read or tell the person the rest did not fit. One
draw in five did this
([readings](../../readings/tool-result-room.md#an-answer-from-cut-results)).

## What to do

1. Keep the brain's log, and repeat the row ten times on the current build, counting the draws
   whose reply describes a file none of whose text reached the context. Write the count and the
   pass rule into the readings before any change.
2. If the count holds, try the result text first: `NO_ROOM_NOTE` could name the file it stands
   for and say that nothing of it was read.

## History

- 2026-10-28: filed from the baseline of the cut-results rows on the `cortexn9` stack.
