# The measurement script reads one field off a line it has whole

**Status:** done 2026-08-27
**Area:** cross-cutting
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)

`scripts/trailwidth.py` reads the `dropped` field's rendering off every captured line and reports
nothing about the line it came out of. The line is right there in the capture, whole, and its
length is the open question [R-337](337-a-bounded-value-leaves-the-line-unbounded.md) waits on:
that entry's trigger is a line whose fields together pass 16,383 rendered characters, the limit the
log driver ends a message at, and it is a trigger precisely because nothing had ever measured a
real line's total width.

The fix is to report the whole line's rendered width beside the field's, per capture, in the same
groups. Two details make it less trivial than it sounds. A capture taken through
`docker compose logs` has a service prefix the line itself never had, so the reported width has to
be the rendering rather than the captured text, which means finding where the formatter's own
output starts. And a line the driver split arrives concatenated in the plainest reading, so a run
that ever produced one would need the `-t` reading to see the split.

It is worth doing because the recall trail is the widest line the brain writes, so if any line in
this deployment approaches that limit it is one of these, and the script that would answer it
exists and runs in fifteen minutes.

## History

- 2026-08-26: opened by the close of
  [R-358](358-the-widest-value-was-never-a-real-line.md), which built a script that captures real
  trail lines and then measures exactly one field of each.
- 2026-08-27: closed, as [ADR-0051 decision 16](../../adr/ADR-0051-log-line-rendering.md).
  `scripts/trailwidth.py` reports the whole line's rendered width beside the field's, per block and
  in the same groups, measured from where the shipped formatter's output starts so a capture's own
  service prefix is not counted. Read off the captures the earlier run already produced: 466 lines,
  1,691 to 1,800 characters, against the 16,383 a container's log driver ends a message at, which
  is the headroom [R-337](337-a-bounded-value-leaves-the-line-unbounded.md) has been waiting on and
  it is a factor of nine. The group table runs backwards, which is the finding: a rank that keeps
  nothing writes the widest `dropped` field and the narrowest line, because a kept hit costs about
  100 characters against a dropped candidate's 73, so the field's own reading points at the wrong
  lines for this question. The `-t` capture this entry suggested for seeing a split line is
  declined with evidence: its stamps fall mid line and inflate the width being measured, and a
  split reads back concatenated in the plain capture, so the width reported is right and only the
  fact of the split is lost. Opened by this close:
  [R-471](471-the-lines-ceiling-is-the-least-sampled-cohort.md).
