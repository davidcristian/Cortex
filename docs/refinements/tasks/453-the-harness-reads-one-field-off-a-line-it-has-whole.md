# The harness reads one field off a line it has whole

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Opened 2026-08-26 by the close of
[R-358](358-the-widest-value-was-never-a-real-line.md), which built a harness that captures real
trail lines and then measures exactly one field of each.

`scripts/trailwidth.py` reads the `dropped` field's rendering off every captured line and reports
nothing about the line it came out of. The line is right there in the capture, whole, and its
length is the open question
[R-337](337-a-bounded-value-leaves-the-line-unbounded.md) is waiting on: that entry's trigger is a
line whose fields together pass 16,383 rendered characters, which is the cliff the log driver ends
a message at, and it is stated as a trigger precisely because nothing had ever measured a real
line's total width. The captures this harness writes are that measurement sitting unread.

**What would close it.** Report the whole line's rendered width beside the field's, per capture,
in the same cohorts. Two details make it less trivial than it sounds. A capture taken through
`docker compose logs` carries a service prefix that the line itself never had, so the reported
width has to be the rendering rather than the captured text, which means finding where the
formatter's own output starts. And a line the driver split arrives concatenated in the plainest
reading, so a run that ever produced one would need the `-t` reading to see the split at all. Both
are small; neither is free.

The reason this is worth doing at all rather than filing and forgetting: the recall trail is the
widest line the brain writes, so if any line in this deployment approaches the cliff, it is one of
these, and the harness that would answer it now exists and runs in fifteen minutes.
