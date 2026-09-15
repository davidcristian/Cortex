# The remedy a refused heading prints does not fit the refusal it follows

**Status:** landed 2026-09-15
**Area:** repo-gates
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)

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
because [R-334](334-a-heading-whose-brackets-are-prose.md) is the entry that has not decided what the
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
- 2026-09-10: the trigger has not fired, for the same reading that keeps
  [R-334](334-a-heading-whose-brackets-are-prose.md) open: no heading in the 725 tracked markdown
  files carries a bracket, so `backlogcheck` has never printed the bracketed refusal at all.
  `scripts/headingshapes.py` still ends every refusal with the one shared `PLAINLY` constant, and
  the wording decision this entry describes is still undecided because the entry it moves with is.
- 2026-09-15: landed as a remedy for the bracketed span alone, the `QUOTED` constant, which names
  the code span: `; quote the brackets in a code span, whose backticks this rule and a renderer
  both drop, or write the heading without them`. The reason this entry gave for filing rather than
  fixing turned out to rest on a wrong premise, which running the reader showed. The escape it was
  waiting on already exists: a code span is one of the shapes `headingshapes.py` documents as
  slugging identically on both sides, and ``## Array index `a[0]` `` passes the gate today, so the
  remedy could name an answer without deciding [R-334](334-a-heading-whose-brackets-are-prose.md).
  The other five refusals keep `PLAINLY`, which fits them. Recorded at the origin record as the
  bracket-remedy addendum, with the sweep it was measured over, 772 markdown files carrying zero
  bracketed headings, and the three mutations it was proved with. The close opened
  [R-677](677-a-double-backtick-code-span-is-torn-apart.md): the remedy names a code span, and
  `CODE_SPAN` reads only the single backtick spelling of one, so a heading quoting brackets in a
  double backtick span is refused and told to do what it did.
