# A count that is short by one names no line to open

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Verified:** 2026-09-12
**Trigger:** a counted mention going short on a file where the reader cannot see which occurrence
went, which is a file spending the value more than the count pins or spending it far apart: the
runbook table row and the fenced recipe forty lines below it are the shape to watch, since the two
readings that would name the line are already written and only the sentence is missing.

Opened 2026-09-12 by the close of
[R-405](405-a-counted-mention-that-finds-nothing-says-nothing.md), which gave a counted mention
that finds none of its set the reading a presence check gets and left the short count as it was.

`crosscheck.check_mention` now has three answers for a counted mention. It holds; it finds none of
the needle, and gets `needles.unfound`, which names the line the carried run stops on and the line
the value is still spelled on; or it finds some but not the pinned number, and gets `found N,
pinned M` and no line at all. That third answer is the common drift, a half applied rename over a
set of two, and it is the one that names nothing: a reader is told a runbook spells the endpoint
once where two are pinned and has to grep the file to find which of the two moved.

The asymmetry is this close's own doing. Before it, neither the short count nor the zero named a
line, so the two answers agreed with each other; now the rarer case is the better reported one. It
is also the cheaper case to report, which is why it went first: a file holding none of the needle
has one run to measure and one value to look for, where a file holding two of three has three
matches and the interesting thing about them is which one is absent, and absence has no line.

**What would close it, and the reason it is not obvious.** The bounded matches are already in hand,
so naming the lines the needle *was* found on costs one sentence: `found 1 on line 34, pinned 2`.
That is honest and it is not the question a reader has. The question is where the missing occurrence
used to be, and the file no longer says. What the file does say is where the value is still spelled
in some other shape, which is exactly `needles.unfound`'s second reading, and running it over a
short count would offer the lines the needle did not match as candidates. Before writing that,
decide whether the candidates are worth the sentence: over the volume runbook the value is spelled
in four places, so the reading would offer three lines and the reader would still be grepping,
which is the same weak form the zero case prints and says nothing about. A count is over one file,
and a per line count is the other half of the same question
([R-406](406-the-carried-run-is-measured-over-a-whole-file.md)) rather than a separate one.

## Trail

- 2026-09-12: opened by the close of
  [R-405](405-a-counted-mention-that-finds-nothing-says-nothing.md), whose second control row
  measured it: one of the volume runbook's two `host.docker.internal:50151` endpoints moved prints
  `found 1, pinned 2` and no line, both before that close and after it. Not fired, there being no
  short count on the real tree; `crosscheck` passes over 91 constants, 109 declaring sites and 300
  mentions, 27 of them pinned to a count.
