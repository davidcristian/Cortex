# The run an unfound needle quotes back is measured over a whole file, so it overstates itself

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Verified:** 2026-09-17

Opened 2026-08-23 by the close of
[R-403](403-a-needles-literal-reddens-the-wrong-entry.md), which measured this while writing the
fault and chose to report the limitation rather than hide it.

`scripts/needles.py`'s `carried` returns the longest opening run of a rendered needle that the
file's text contains, and the fault quotes it back so a reader can see where the file stops
agreeing. A `Mention` names a file and not a line, so that run is taken over the whole text, and a
prefix satisfied on some **other** line makes it longer than the divergence in the line the reader
is actually looking at. Measured on the case the close was written for: with
`docker/docker-compose.yml`'s seam publish moved to `0.0.0.0`, the run over the needle
`"127.0.0.1:50051:50051"` still reaches `"127.0.0.1:`, carried by the redis publish forty lines
below, where the divergence in the intended line is at its second character.

**Why it was left.** The run is the weaker of the fault's two readings and it is worded to be true
of what was measured, "carrying no more of it than", so it misleads nobody who reads it literally.
The claim that carries the fault is whether the file still spells the constant's own value, which
is unaffected by this. Sharpening the run is a separate question about what a mention is scoped to,
and answering it inside a close about misattribution would have buried it.

**What would close it, and the reason it is not obvious.** The narrow fix this entry used to
propose, the longest opening run taken per line, does not fix its own case. Measured 2026-09-17 on
the replay above, line 59 carries only the needle's opening `"`, so the best line by opening run is
line 100 again, carrying `"127.0.0.1:`. The drift is in the needle's opening characters, and an
opening run cannot find a line whose opening moved. What does find it is the run from both ends:
over the lines that do not hold the whole needle, take the opening run and the closing run on each
line and pick the line where the two together cover the most of it. Line 59 covers 14 of the
needle's 23 characters that way (`"` and `:50051:50051"`), line 100 covers 12, and no other line
ties. That is still a heuristic rather than a reading, and a needle spanning two lines has no best
line at all.

The design question the entry filed with has been answered, in the other direction and by a
different change, so what remains is narrower than the paragraph above. A mention is a claim about a
**file**: five of the registry's 313 mentions render a template that crosses a line boundary, and
two of them were written that way on purpose, holding `- "--threads"` and the substitution on the
line under it as one needle rather than as a relation between two compose keys
(`scripts/subagentcouplings.py`, the ADR-0004 thread-flag addendum). A per line run is therefore not
available for every needle, and the fix is two shapes: the run from both ends over the best line
where the rendered needle holds no newline, and the whole file run, which is what prints today,
where it does. Whether a reader is better served by a reading that changes shape with the needle is
the question to answer before writing it.

**What the next slot builds.** A per line reading in `scripts/needles.py`, taken from both ends of
the needle over the lines that do not hold it whole, used by `unfound` for a needle holding no
newline and naming that line in place of the whole file run's stop; a needle holding a newline
keeps today's reading. The same reading is what the short count in
[R-656](656-a-short-count-names-no-line.md) is missing, so one landing can close both. It has to
settle ties (two lines covering the same number of characters) before it names one line, and
`needles.py` is at 250 of its 300 lines, so the reading most likely goes in a module of its own.

Re-derive before starting: this description is a reading of `scripts/needles.py` and
`scripts/crosscheck.py` that has been corrected twice, and the tree moves under it.

## Trail

- 2026-09-10: re-derived, as the paragraph above asks, and still not fired. `needles.carried` still
  grows the run one character at a time against the whole of `text` and takes no line number, and a
  `Mention` still names a path rather than a line, so both halves of the limitation stand as
  written. No mention in the registry renders a multi-line template, which is the other half of the
  trigger. Nobody has been misled by a quoted run either, there being no recorded instance of one
  being acted on.
- 2026-09-12: re-derived again, and the reading corrected in three places. **The run names a line
  now, and on this entry's own case it is the wrong line.** Replanting the measurement the body
  quotes, with `docker/docker-compose.yml`'s seam publish moved to `0.0.0.0`, the fault reads
  `carrying no more of it than '"127.0.0.1:', which stops on line 100`, and line 100 is the redis
  publish. The line that moved is 59, and the whole message names it nowhere: the value reading
  points at line 82, the healthcheck that dials the port. So the overstated run is no longer only a
  string a careful reader discounts; it is a line number, and the sentence hands the reader a line
  to open that has nothing to do with the drift. The 2026-09-10 trail said the run takes no line
  number, which was already wrong when it was written (ADR-0029 run-line addendum).
  **The second half of the trigger has fired.** Five of the registry's 300 mentions render a
  template carrying a newline, two of them added today to hold `--threads` beside the substitution
  under it, and the body's claim that the scan renders no multi-line template is now false. That
  settles the scope question this entry was waiting on, against the fix it proposed: a mention is a
  claim about a file, so a per line run cannot be the only kind of run. Left open, with the
  narrowed statement above, because nobody has yet acted on a quoted line.
- 2026-09-17: re-derived, and re-filed as actionable. The reader half of the old trigger, somebody
  acting on the quoted line and editing the wrong one, is not something the tree records, since a
  drift is repaired in the commit that caused it. Stated as something a replay can answer, it is a
  fault naming a line the drift is not on while naming the drifted line nowhere, and that is what
  the replay prints: `docker/docker-compose.yml`'s seam publish moved to `0.0.0.0` on a scratch
  export of the tree still reads `carrying no more of it than '"127.0.0.1:', which stops on line
  100`, with the value reading on line 82 and line 59 unnamed. The body's remedy was also wrong
  about its own case: the longest opening run per line picks line 100 as well, and only a run from
  both ends picks 59, measured over the same replay. The registry holds 313 mentions today, and the
  five that cross a line boundary are the same five.
