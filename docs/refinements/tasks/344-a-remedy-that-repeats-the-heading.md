# The remedy a refused heading prints does not fit the refusal it follows

**Status:** done 2026-09-15
**Area:** repo-checks
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)

Every refusal `scripts/headingshapes.py` prints ended in one shared remedy, the `PLAINLY` constant:
`; write it as plain text under leading hashes, so the source is what a renderer slugs`. That fits
five of the six shapes, each of which is markup the author can stop writing. It does not fit the
sixth. A heading reading `## Array index a[0]` is already plain text under leading hashes and has
no markup at all, so the author is told to do the thing they did.

The origin record overstated this: it said a heading that means its brackets literally has to be
written another way "and the message says so". The message says the heading brackets a span, which
is true, and then prints a remedy that describes the heading it is refusing.

It is a wording decision rather than a one-line fix, because the remedy cannot name the answer
while [R-334](334-a-heading-whose-brackets-are-prose.md) has not decided what the answer is. So the
smallest defensible version is a remedy per shape, replacing one shared constant with one sentence
per refusal.

## History

- 2026-08-20: Opened by a review of the bracketed span refusal, which found the printed remedy
  unusable for the one shape that refusal newly reaches, and the origin record claiming the
  opposite.
- 2026-09-10: The trigger has not fired, for the same reason
  [R-334](334-a-heading-whose-brackets-are-prose.md) stays open: no heading in the 725 tracked
  markdown files has a bracket, so `backlogcheck` has never printed the bracketed refusal at all.
  `scripts/headingshapes.py` still ends every refusal with the one shared `PLAINLY` constant.
- 2026-09-15: Fixed as a remedy for the bracketed span alone, the `QUOTED` constant, which names
  the code span: `; quote the brackets in a code span, whose backticks this rule and a renderer
  both drop, or write the heading without them`. The reason this entry gave for filing rather than
  fixing rested on a wrong premise, which running the reader showed: the escape it was waiting on
  already exists, a code span being one of the shapes `headingshapes.py` documents as producing the
  same slug on both sides, and ``## Array index `a[0]` `` passes today. The other five refusals
  keep `PLAINLY`. The origin record states it as its decision 10; the review it was measured over
  found zero bracketed headings in 772 markdown files, and three mutations proved it. The close
  opened [R-677](677-a-double-backtick-code-span-is-torn-apart.md): the remedy names a code span,
  and `CODE_SPAN` reads only the single backtick form, so a heading quoting brackets in a double
  backtick span is refused and told to do what it did.
