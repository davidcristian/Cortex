# An unfound needle whose value is an ordinary word reads prose as the value still spelled

**Status:** open, fix when it bites
**Area:** repo-gates
**Trigger:** a reader of a `crosscheck` fault over a word-valued entry following its second
reading to a line of prose and changing the wrong constant, or a second registered entry whose
value is a word the far file's own docstrings use.
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-02 by the close of
[534](534-the-declared-kind-word-has-no-site-to-hold-it.md), whose first mutation showed it.

`needles.unfound` gives an unfound needle two readings: how much of the needle the file carries
and where that run stops, and whether the file still spells the value as a token of its own, with
the line it is nearest on. The second reading exists to say that what moved is shape rather than
value, which points the reader at a neighbouring constant (ADR-0023 bind-host addendum). It counts
every bounded occurrence of the rendered value in the file, and for a value that is an ordinary
word the file's own prose supplies them. With the enum value renamed alone, the gate reported that
`provenance.py` still spells `sender` as a token of its own in seven places, the nearest on a
docstring line reading "by sender must not sweep a URI", and concluded that what moved was likely
shape and the constant to change might not be the one named. What moved was the value, and the
first reading, stopping at `SENDER = "` on the member's own line, said so.

**Why it was left.** The verdict is right and the first reading is right; only the hedge is wrong,
and it is wrong for a value the file uses as a word. This mutation is the first time a run here
showed the hedge misreading prose. Narrowing the second reading, say to occurrences inside quotes
or on a line that also carries part of the needle, is a design question about what counts as a
spelling of a value, and one entry is not enough to settle it on.

**What would close it.** Decide what a spelling of the value looks like when the value is a word,
and change `unfound` so the hedge is stated only when one is found; or state both readings without
concluding which moved, and leave the conclusion to the reader. Either way the suite's cases for
`unfound` gain one over a value the file also uses in prose.

## Trail

- 2026-09-02: opened by the close of
  [534](534-the-declared-kind-word-has-no-site-to-hold-it.md), recorded in its ADR-0029
  declared-kind-word addendum.
