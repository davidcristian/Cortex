# One regex stands in for a renderer's slugger

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)
**Trigger:** the first heading written in one of the five shapes below, or any report from this gate against a heading that a renderer resolves fine, either of which turns a measured absence into a live disagreement.

Opened 2026-08-17 by the close of [R-276](276-repo-wide-anchor-check.md), which pointed the anchor
check at every markdown document in the repo instead of at the two backlog indexes. Judging more
documents means the slug rule has to be right about more headings, and the rule is
`DROPPED.sub("", heading.lower()).replace(" ", "-")` over the raw source line: lowercase it, drop
every character that is not a word character, a space or a hyphen, then hyphenate the spaces. What
a renderer does instead is slug the **rendered** text of the heading, which is not the same string.

**It was measured, not assumed.** The 1,918 headings across the repo's 389 markdown files were
surveyed for the shapes where the two disagree, and the two shapes that are present agree exactly.
Fourteen headings carry an ampersand and seven carry an arrow; both drop a character standing
between two spaces, and neither the renderer nor this rule collapses the pair of hyphens that
leaves, so `Risks & notes` is `risks--notes` on both sides. Both are now pinned by a test. Six
files repeat a heading, which the numbering from the second occurrence covers, and the host index's
runbook fences are full of shell comments, which the fence rule covers.

**Five shapes would disagree and none of them is in the tree.** Four are headings this rule reads
too literally:

- A heading containing a link, meaning bracketed text followed by a parenthesised target. A
  renderer slugs the bracketed text alone; this rule slugs the text and the target both, so the
  anchor it expects has the target path welded onto the end of it. The example cannot be written
  out here, because the scanner reads a link in a code span as a link and would hold this file to
  resolving it.
- A heading containing an HTML tag, `## <kbd>Ctrl</kbd>+N`, where a renderer drops the tags and
  this rule keeps their letters.
- A heading closed with trailing hashes, `## Title ##`, which markdown allows and a renderer
  strips; here the hashes vanish and the space before them becomes a trailing hyphen.
- A heading using underscores for emphasis, `## _emphasis_`, where the underscore is a word
  character to this rule and a formatting mark to a renderer.

The fifth is a setext heading, written as an underline of `=` or `-` rather than with a leading
hash. That one is invisible to `anchors()` entirely, so a document written that way would offer no
anchors at all and every pointer into it would be reported. It is the loudest of the five and the
cheapest to notice.

**What would close it.** Rendering the inline markdown of a heading before slugging it, which is
four small transforms (drop HTML tags, keep a link's text and drop its target, strip emphasis
marks, strip trailing hashes) plus reading setext headings in `anchors()`. It is contained to
`backloganchors.py` and needs no dependency; a markdown library would be a heavier answer than the
problem, and this repo's gates carry no third-party parsers on purpose. The reason it waits is that
the tree has none of these today, and a transform written against no example is a guess that the
gate cannot fail on, which is this repo's definition of a defect in a gate.

## Trail

- 2026-08-17: written down by the close of [R-276](276-repo-wide-anchor-check.md), which widened
  the anchor check from two documents to every markdown file in the repo and so made the fidelity
  of the slug rule matter everywhere rather than in one generated index.
