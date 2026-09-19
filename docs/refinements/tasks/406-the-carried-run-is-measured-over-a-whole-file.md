# The run an unmatched search text quotes back is measured over a whole file, so it overstates itself

**Status:** done 2026-09-17
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`scripts/needles.py`'s `carried` returns the longest opening run of a rendered search text that the
file's text contains, and the fault message quotes it back so a reader can see where the file stops
agreeing. A `Mention` names a file and not a line, so that run is taken over the whole text, and a
prefix satisfied on some other line makes it longer than the difference in the line the reader is
actually looking at. Measured on the case the fault was written for: with
`docker/docker-compose.yml`'s brain publish moved to `0.0.0.0`, the run over the search text
`"127.0.0.1:50051:50051"` still reaches `"127.0.0.1:`, matched by the redis publish forty lines
below, where the difference in the intended line is at its second character.

The narrow fix first proposed, the longest opening run taken per line, does not fix its own case.
Measured 2026-09-17 on the replay above, line 59 contains only the search text's opening `"`, so
the best line by opening run is line 100 again. The change is in the search text's opening
characters, and an opening run cannot find a line whose opening moved. What does find it is the run
from both ends: over the lines that do not contain the whole search text, take the opening run and
the closing run on each line and pick the line where the two together cover the most of it. Line 59
covers 14 of the search text's 23 characters that way (`"` and `:50051:50051"`), line 100 covers
12, and no other line ties.

A match is a claim about a file: five of the registry's 313 matches render a template that crosses
a line boundary, two of them written that way on purpose. So a per-line run is not available for
every search text, and the fix is two shapes: the run from both ends over the best line where the
rendered search text contains no newline, and the whole-file run where it does.

## History

- 2026-08-23: opened by the close of
  [R-403](403-a-needles-literal-reddens-the-wrong-entry.md), which measured this while writing the
  fault message and chose to report the limitation rather than hide it.
- 2026-09-10: checked again and still not fired. `needles.carried` still grows the run one
  character at a time against the whole of `text` and takes no line number, and a `Mention` still
  names a path rather than a line. No match in the registry renders a multi-line template, which
  is the other half of the trigger. Nobody has been misled by a quoted run, there being no recorded
  instance of one being acted on.
- 2026-09-12: checked again, and the reading corrected in three places. The run names a line now,
  and on this entry's own case it is the wrong line. Replanting the measurement above, the fault
  reads `carrying no more of it than '"127.0.0.1:', which stops on line 100`, and line 100 is the
  redis publish. The line that moved is 59, and the whole message names it nowhere: the value
  reading points at line 82, the healthcheck that dials the port. So the overstated run is no
  longer only a string a careful reader discounts; it is a line number, and the sentence hands the
  reader a line to open that has nothing to do with the change. The 2026-09-10 entry said the run
  takes no line number, which was already wrong when it was written (ADR-0042). The second half of
  the trigger has fired: five of the registry's 300 matches render a template containing a newline,
  two of them added that day to cover `--threads` beside the substitution under it. That settles
  the scope question against the fix first proposed: a match is a claim about a file, so a per-line
  run cannot be the only kind of run. Left open because nobody had yet acted on a quoted line.
- 2026-09-17: checked again and re-filed as actionable. The reader half of the old trigger,
  somebody acting on the quoted line and editing the wrong one, is not something the tree records,
  since a change is repaired in the commit that caused it. Stated as something a replay can answer,
  it is a fault naming a line the change is not on while naming the changed line nowhere, and that
  is what the replay prints: the brain publish moved to `0.0.0.0` on a scratch export of the tree
  still reads `carrying no more of it than '"127.0.0.1:', which stops on line 100`, with the value
  reading on line 82 and line 59 unnamed. The remedy in the body was also wrong about its own case:
  the longest opening run per line picks line 100 as well, and only a run from both ends picks 59.
  The registry has 313 matches today, and the five that cross a line boundary are the same five.
- 2026-09-17: closed. `scripts/linereadings.py` reads every line from both ends of the search text,
  and `needles.unfound` uses it for every search text without a newline. The replay above now names
  line 59 with 14 of the search text's 23 characters, reads the port on the same line and gives the
  result that shape moved; the whole-file run is kept only for the five search texts that span two
  lines, filed as [R-680](680-a-needle-spanning-two-lines-keeps-the-whole-file-run.md). The
  measurement over every registered search text, the half-length minimum and the reason no margin
  is used are in
  [the registry readings](../../readings/constant-registry.md#which-line-a-fault-names). The same
  reading closed [R-656](656-a-short-count-names-no-line.md).
