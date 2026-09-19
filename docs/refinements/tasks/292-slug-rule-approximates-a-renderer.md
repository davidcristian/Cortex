# One regex substitutes for a renderer's slug rule

**Status:** done 2026-08-18
**Area:** repo-checks
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)

Opened 2026-08-17 by the close of [R-276](276-repo-wide-anchor-check.md), which pointed the anchor
check at every markdown document in the repo instead of at the two backlog indexes. Judging more
documents means the slug rule has to be right about more headings, and the rule is
`DROPPED.sub("", heading.lower()).replace(" ", "-")` over the raw source line: lowercase it, drop
every character that is not a word character, a space or a hyphen, then hyphenate the spaces. A
renderer instead slugs the rendered text of the heading, which is a different string.

It was measured rather than assumed. The 1,918 headings across the repo's 389 markdown files were
surveyed for the shapes where the two disagree, and the two shapes present agree exactly. Fourteen
headings contain an ampersand and seven contain an arrow; both drop a character between two spaces,
and neither the renderer nor this rule collapses the pair of hyphens that leaves, so `Risks & notes`
is `risks--notes` on both sides. Both are asserted by a test. Six files repeat a heading, which the
numbering from the second occurrence covers, and the host index's runbook fences are full of shell
comments, which the fence rule covers.

Five shapes would disagree and none is in the tree. Four are headings this rule reads too literally:
a heading containing a link, where a renderer slugs the bracketed text alone while this rule slugs
the text and the target both; a heading containing an HTML tag, `## <kbd>Ctrl</kbd>+N`, where a
renderer drops the tags and this rule keeps their letters; a heading closed with trailing hashes,
`## Title ##`, which a renderer strips while here the hashes vanish and the space before them
becomes a trailing hyphen; and a heading using underscores for emphasis, `## _emphasis_`, where the
underscore is a word character to this rule and a formatting mark to a renderer. The fifth is a
setext heading, written as an underline of `=` or `-`, which `anchors()` does not see at all, so a
document written that way would offer no anchors and every pointer into it would be reported.

## History

- 2026-08-17: Written down by the close of [R-276](276-repo-wide-anchor-check.md), which widened
  the anchor check from two documents to every markdown file in the repo.
- 2026-08-18: Became `scripts/headingshapes.py`, which refuses those shapes rather than rendering
  them, the opposite of what this entry proposed and argued in the origin record's decision 10. The
  reason the entry gave for waiting is the reason emulation was declined: a transform written
  against no example is a guess, and a wrong transform yields a wrong anchor, which is a silent
  accept, where a refusal fails loudly in both directions. Checking it again found the measured
  absence still true in a bigger tree (404 files, 1,993 headings, 267 fragments) and found a sixth
  shape this entry did not list, an entity reference, absent too and now refused with the rest.
  Wiring the refusal into `backloganchors.py` took it to 334 lines, so what a heading is moved into
  its own module. A document containing a refused heading now has its anchors left unknown, the way
  a broken index does. Opened [307](307-shortcut-reference-link-in-a-heading.md), the one case the
  six do not cover.
