# The reader's needles are not tied to the sink that writes them

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Opened 2026-08-26 by the close of
[R-358](358-the-widest-value-was-never-a-real-line.md), which added a second module to `scripts/`
that reads the brain's log lines and spells two of the brain's own strings to find them.

`scripts/trailwidth.py` looks for `memory.recall`, the message `LoggingRecallSink` writes, and for
a field called `dropped`, the key that sink attaches its candidate list under. Both are written out
here as literals and neither is tied to the declaration. Rename either in
`brain/packages/memory/src/cortex_memory/audit.py` and this reader stops finding lines; what it
does then is refuse, with `no memory.recall line carrying a dropped field`, which is the right
shape of failure and still tells an operator the stack is broken when the reader is.

That is exactly the coupling `crosscheck.py` exists for, and `logcouplings.py` already ties this
same sink's `session_id` spelling back to the declaration in `log_fields.py`. The two literals here
are the same kind of fact and are registered nowhere.

**What would close it.** A registry entry tying `trailwidth.TRAIL_MESSAGE` to the message argument
of the `_logger.info` call in that sink, and `trailwidth.TRAIL_FIELD` to the key it builds its
field dict under. `logcalls.py` already parses that module for what a call attaches, which is most
of the reading, so the work is the registration rather than a new parser.

**Why it is not urgent.** The reader gates nothing, so a stale needle costs a hand run and a clear
refusal rather than a wrong green. It is filed because the cost of registering it is small and the
next rename is where it would be noticed.
