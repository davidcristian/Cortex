# A shortcut reference link in a heading is the one shape the refusal cannot see

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)
**Trigger:** the first link reference definition written anywhere in this repo, a line whose whole content is a bracketed label, a colon and a target. Until one exists, the shape below renders as literal brackets and both readings agree.

Opened 2026-08-18 by the close of [292](292-slug-rule-approximates-a-renderer.md), which made
`scripts/headingshapes.py` refuse six heading shapes whose anchor the slug rule cannot work out.
Five of the six are recognised by a mark that is present in the heading itself. The sixth family,
links, is recognised by a bracketed span **followed** by an opening parenthesis or an opening
bracket, which covers an inline link, an image and a collapsed reference link, and misses the
**shortcut** form: a bracketed label alone, which markdown resolves against a link reference
definition somewhere else in the document.

That form disagrees the same way the others do. A renderer slugs the label's text and this rule
slugs the brackets away too, which happens to agree, but the rendered text is the label while the
source is the label plus its brackets, and any label carrying markdown of its own reopens the whole
question. The reason it is not refused today is that recognising it needs the document's link
reference definitions, not the heading alone, which is the first thing in this gate that would.

**It is unreachable in this tree, measured rather than assumed.** A survey of all 404 markdown
files on the day this was written found **zero** link reference definitions and **zero** headings
carrying a bracketed span that is not already an inline link. With no definitions anywhere, a
bracketed label in a heading renders as its own literal brackets, which this rule drops exactly as
a renderer does, so the two readings agree and there is nothing to report.

**What would close it.** Collect each document's link reference definitions in one pass, then
refuse a heading whose bracketed label names one. The alternative, and probably the better one, is
to refuse a bare bracketed span in a heading outright, definitions or not, since a heading that
looks like a link and is not one misleads a reader before it misleads this gate; that costs one
regex and no second pass, at the price of banning a literal bracket in a heading. Decide which
before writing either, and prove the change fails on a synthetic heading the way the six already
refused were proved.

## Trail

- 2026-08-18: opened by the close of [292](292-slug-rule-approximates-a-renderer.md), whose
  re-derivation of the slug rule's fidelity found this residue beside the six shapes it refused.
