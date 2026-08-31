# The reader's needles are not tied to the sink that writes them

**Status:** landed 2026-08-27
**Area:** repo-gates
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Opened 2026-08-26 by the close of
[R-358](358-the-widest-value-was-never-a-real-line.md), which added a second module to `scripts/`
that reads the brain's log lines and spells two of the brain's own strings to find them.

`scripts/trailwidth.py` looks for `memory.recall`, the message `LoggingRecallSink` writes, and for
a field called `dropped`, the key that sink attaches its candidate list under. Both are written out
here as literals and neither is tied to the declaration. Rename either in
`brain/packages/memory/src/cortex_memory/audit.py` and this reader stops finding lines; what it
does then is fail, with `no memory.recall line carrying a dropped field`, which is the right
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

## Trail

- 2026-08-26: opened by the close of
  [R-358](358-the-widest-value-was-never-a-real-line.md), which added a second module to `scripts/`
  that reads the brain's log lines and spells two of the brain's own strings to find them.
- 2026-08-27: **landed**, as the [ADR-0038 tied-needle
  addendum](../../adr/ADR-0038-ranked-recall.md) and two entries in `scripts/logcouplings.py`, the
  registry part whose subject is a name a log line is written with. `TRAIL_MESSAGE` and
  `TRAIL_FIELD` are the declaring sites and the sink holds the mentions, which is the first entry
  in the registry whose declaring side gates nothing: the argument for holding it is
  `fixturecouplings.py`'s, that a value no suite runs on every commit needs the registry more than
  a shipped one does. **One half of this entry's claim was stale**: a rename of the message alone
  never stopped the reader finding lines, the plain formatter putting the same word on every line
  twice, once as
  the logger's tail and once as the message, so the reader would have gone on working by accident.
  The field is the needle whose rename really does stop the reader. The message's needle is written as the emitting
  call for exactly that reason. Two Python places being one language, the entries stand on the far
  sides that were already there and unheld, the memory runbook and the gates module contract, which
  is the same answer the subagent flag rule reached rather than arranging the entry past the rule.
  Opened by this close:
  [R-469](469-the-trails-logger-name-is-spelled-in-three-places-and-held-in-none.md) and
  [R-470](470-the-reader-assumes-the-plain-rendering.md).
- 2026-08-27: the accident recorded above is gone. Measuring the whole line meant finding where the
  formatter's output starts, so a trail line now qualifies by carrying the message where the
  formatter puts one rather than anywhere in the text
  ([R-453](453-the-harness-reads-one-field-off-a-line-it-has-whole.md), ADR-0038 whole-line
  addendum). The message needle registered here matters from that day on: rename the message
  alone and the reader stops finding lines, which is what this entry claimed and what was not yet
  true when it closed.
