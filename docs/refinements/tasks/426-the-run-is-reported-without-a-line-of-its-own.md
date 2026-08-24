# The run an unfound needle reports has no line, though choosing between matches computes one

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-25 by the close of
[R-414](414-the-still-spelled-reading-does-not-say-where.md), which gave the value reading a line
and left the run reading without one.

An unfound needle now carries two readings and they are told in two different ways. The value
reading names how many places spell the value, which line the nearest one is on, and what that line
says. The run reading, the longest opening piece of the needle the file carries anywhere, is still
quoted as text alone: `carrying no more of it than '`DEFAULT_STOP_GRACE_S` (1'`. Where in the file
that run stops is never said, even though `needles.nearest` locates every occurrence of it in order
to pick which value match to quote, and then discards the positions.

The distance between the two is the evidence a reader is actually weighing. A value spelled on the
line where the run stops is the strong form of "what moved is shape". A value seventy lines away,
which is the real case this came out of, is the weak form, and the reader can only see which they
have by opening the file. Saying both lines would put that comparison in the message.

**Why it was left.** The close it came out of was about the value reading, and giving the run a
line raises a question that reading did not have to answer: a run is a prefix, so it may be carried
in several places, and the one `needles.py` already documents as making the run longer than the
divergence is the compose publish's `"127.0.0.1:` satisfied by the redis publish two dozen lines
below. Naming one line for it therefore has to say which, and the honest answer may be the last
occurrence, the nearest to the quoted value, or a count the way the value reading now carries one.
Deciding that inside a close about where a value sits would have hidden it.

**What would close it.** Decide which occurrence of the run a line should name, and whether the two
lines should be compared for the reader (`the run stops on line 115 and the value is 71 lines
below`) or merely both stated. Weigh the message length while there: the fault already carries a
stem, two readings, one quoted line and the entry's `why`, and a second quoted line would be the
point at which a fault stops being one sentence. The cheapest honest shape may be a line number for
the run with no second quote, since the run's text is already in the message and only its place is
missing.

## Trail

- 2026-08-25: opened by the close of
  [R-414](414-the-still-spelled-reading-does-not-say-where.md), which spent the run's positions to
  choose which value match to quote and never spent them on the run itself.
