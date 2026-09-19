# A count that is short by one names no line to open

**Status:** done 2026-09-17
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`crosscheck.check_mention` has three answers for a counted mention. It passes; it finds none of the
search text and gets `needles.unfound`, which names the line the longest run stops on and the line
the value is still written on; or it finds some but not the expected number and gets
`found N, pinned M` and no line at all. That third answer is the common mismatch, a half applied
rename over a set of two, and it named nothing: a reader was told that a runbook writes the endpoint
once where two are expected, and had to grep the file to find which of the two moved.

The asymmetry came from the change that added the first reading. Before it, neither the short count
nor the zero named a line. The zero was the cheaper case to report, which is why it went first: a
file with none of the search text has one run to measure and one value to look for, where a file
with two of three has three matches and the interesting thing is which one is absent.

**What the entry had wrong,** measured 2026-09-17 on a scratch copy of the tree with the volume
runbook's second endpoint, line 48, renamed to `host.docker.internal:50152`. The entry said the file
no longer says where the occurrence went, and that `needles.unfound`'s value reading was the only
candidate. The value reading cannot find a renamed occurrence at all, because the rename is what
took the value off that line: `50151` is still written on lines 12, 13, 34, 76 and 97, six places
before the change rather than the four this entry counted, and none of them is the line that moved.
The search text itself is nearly all still there: line 48 has 25 of its 26 characters as an opening
run. The next lines have 21 (line 78) and 20 (lines 31 and 103), each prose naming the host with
`host.docker.internal:` or without the colon, so the margin is four characters. A half applied
rename does leave a line, and it is the line with the longest run of the search text among the lines
that do not have it whole; only a deleted occurrence leaves none.

**What closed it.** A wrong count now names the lines it found, and a short one adds a per-line
reading over what those leave. The renamed-runbook replay reads `found 1 (on line 12), pinned 2;
outside those, the file is carrying the most of it on line 48, 25 of its 26 characters`. The
threshold question was answered by measurement rather than by a margin: no margin separates a
deleted occurrence from an edited one, so the message names the line with its share and its words
and never says the occurrence moved there, and a line with less than half the search text is not
named (ADR-0042 decision 23). With line 48 deleted instead, the message names line 77 and quotes its
prose. Summing the runs from both ends is an upper bound rather than an alignment: on line 48 the
opening 25 and a closing `1` found elsewhere on the line reach the full 26 without the line having
it, so the reading caps the sum.

## History

- 2026-09-12: opened by the close of
  [R-405](405-a-counted-mention-that-finds-nothing-says-nothing.md), whose second control row
  measured it: one of the volume runbook's two `host.docker.internal:50151` endpoints moved prints
  `found 1, pinned 2` and no line, both before that change and after it. Not fired, there being no
  short count on the real tree; `crosscheck` passes over 91 constants, 109 declaring sites and 300
  mentions, 27 of them with an expected count.
- 2026-09-17: checked again, and re-filed as actionable. The trigger waited on a count going short
  where the reader cannot see which occurrence went, and a mismatch of that kind is repaired in the
  commit that makes it, so the tree never records one. Stated as something a replay can answer, it
  is a short count on a file whose expected occurrences are far apart, and the volume runbook is
  that file today (lines 12 and 48). `crosscheck` passes over 92 constants, 110 declaring sites and
  313 mentions, 27 of them with an expected count.
- 2026-09-17: done, together with
  [R-406](406-the-carried-run-is-measured-over-a-whole-file.md). The two were separate faults on
  separate branches, the zero case naming a line and the wrong one, the short case naming none, and
  one reading serves both.
