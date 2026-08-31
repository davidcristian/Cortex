# The remedy a refused heading prints does not fit the refusal it follows

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)
**Trigger:** the first heading refused for its brackets that is already plain text under leading
hashes, meaning `backlogcheck` printing the bracketed refusal at a heading somebody wrote on
purpose rather than at a link.

Opened 2026-08-20 by a review of the change that made `scripts/headingshapes.py` refuse a bracketed
span with or without a target. Every refusal the gate prints ends in one shared remedy, the
`PLAINLY` constant: `; write it as plain text under leading hashes, so the source is what a
renderer slugs`. That fits five of the six shapes, each of which is markup the author can simply
stop writing. It does not fit the sixth as the rule now stands. A heading reading
`## Array index a[0]` is already plain text under leading hashes and carries no markup at all, so
the author is told to do the thing they did, and the sentence names no way out.

The origin record overstates this in one sentence. Its bracket addendum says a heading that means
its brackets literally now has to be written another way "and the message says so". The message
says the heading brackets a span, which is true, and then prints a remedy that describes the
heading it is refusing. Neither half tells the author what to write instead.

**Why this is a wording decision and not a one line fix.** The remedy cannot simply name the answer,
because [R-334](334-a-heading-that-means-its-brackets.md) is the entry that has not decided what the
answer is: rewriting the heading, an escape the rule honours, or a per line allow marker. A remedy
that names an escape before one exists is worse than a remedy that fits badly. So the two move
together, and the smallest defensible version of this is a per shape remedy, replacing one shared
constant with one sentence per refusal, which is what the constants were already shaped for.

**What would close it.** Either a remedy per shape, where the bracketed one says what a heading that
means its brackets is to do once that is settled, or a decision that the shared remedy is right and
the origin record's sentence about the message is the half that is wrong. The suite already spells
every printed line out literally, so a reworded remedy is a visible change rather than a silent one.

## Trail

- 2026-08-20: opened by a review of the bracketed span refusal, which found the printed remedy
  unactionable for the one shape that refusal newly reaches and the origin record claiming the
  opposite.
