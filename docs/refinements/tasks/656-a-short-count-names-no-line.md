# A count that is short by one names no line to open

**Status:** landed 2026-09-17
**Area:** repo-gates
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

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
matches and the interesting thing about them is which one is absent.

**What would close it.** The bounded matches are already in hand, so naming the lines the needle
*was* found on costs one sentence: `found 1 on line 12, pinned 2`. That is honest and it is not the
question a reader has, which is where the missing occurrence went.

This entry used to answer that the file no longer says, and that `needles.unfound`'s second reading
(where the value is still spelled) was the only candidate. Both halves were wrong, measured
2026-09-17 on a scratch export of the tree with the volume runbook's second endpoint, line 48,
renamed to `host.docker.internal:50152`. The value reading cannot find a renamed occurrence at all,
because the rename is what took the value off that line: `50151` is still spelled on lines 12, 13,
34, 76 and 97 (six places before the drift, not the four this entry counted), and none of them is
the line that moved. The needle itself, though, is nearly all still there: line 48 carries 25 of
its 26 characters as an opening run. The next lines carry 21 (line 78) and 20 (lines 31 and 103),
each of them prose naming the host with `host.docker.internal:` or without the colon, so the margin
is four characters and a threshold has to be chosen against prose like that. So a half applied
rename does leave a line, and it is the line with the longest run of the needle among the lines
that do not hold it whole. Only a deleted occurrence leaves none, and there the sentence can say
that no line comes close.

**What the next slot builds.** The per line reading
[R-406](406-the-carried-run-is-measured-over-a-whole-file.md) now specifies, taken from both ends
of the needle over the lines that do not hold it whole, called from the short count branch of
`crosscheck.check_mention` as well as from `unfound`, naming the best line when one covers more
than a threshold of the needle and saying none does otherwise. The two entries are separate faults
on separate branches: the zero case names a line and it is the wrong one, the short case names
none. What joins them is that one reading serves both, and in the measured short case even the
opening run alone finds the line, since a rename moves the value at the needle's end. Summing the
two runs is an upper bound rather than an alignment: on line 48 the opening 25 and a closing `1`
found elsewhere on the line reach the needle's full 26 without the line holding it, so the reading
has to cap the sum or take the closing run only after the opening one ends.

## Trail

- 2026-09-12: opened by the close of
  [R-405](405-a-counted-mention-that-finds-nothing-says-nothing.md), whose second control row
  measured it: one of the volume runbook's two `host.docker.internal:50151` endpoints moved prints
  `found 1, pinned 2` and no line, both before that close and after it. Not fired, there being no
  short count on the real tree; `crosscheck` passes over 91 constants, 109 declaring sites and 300
  mentions, 27 of them pinned to a count.
- 2026-09-17: re-derived, and re-filed as actionable. The trigger waited on a count going short
  where the reader cannot see which occurrence went, and a drift of that kind is repaired in the
  commit that makes it, so the tree never records one. Stated as something a replay can answer, it
  is a short count on a file whose pinned occurrences are far apart, and the volume runbook is that
  file today (lines 12 and 48). The replay prints `found 1, pinned 2` and no line, as on
  2026-09-12. The body's reason for not naming a line was refuted on the same replay: the renamed
  line keeps 25 of the needle's 26 characters, so it has a line, and the value reading the body
  proposed as the candidate source cannot find it. `crosscheck` passes over 92 constants, 110
  declaring sites and 313 mentions, 27 of them pinned to a count.
- 2026-09-17: landed with [R-406](406-the-carried-run-is-measured-over-a-whole-file.md). A wrong
  count now names the lines it found, and a short one adds the per-line reading over what those
  leave: the renamed runbook replay reads `found 1 (on line 12), pinned 2; outside those, the file is
  carrying the most of it on line 48, 25 of its 26 characters`. The threshold question was answered
  by measurement rather than by a margin: no margin separates a deleted occurrence from an edited
  one, so the fault names the line with its share and its words and never says the occurrence moved
  there, and a line carrying less than half the needle is not named (ADR-0023 per-line run
  addendum). With line 48 deleted instead, the fault names line 77 and quotes its prose.
