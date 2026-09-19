# A heading whose link is a shortcut reference is not refused

**Status:** done 2026-08-20
**Area:** repo-checks
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)

`scripts/headingshapes.py` refuses six kinds of heading whose anchor the slug rule cannot work out.
Five are recognised by a character in the heading itself. The sixth, a link, was recognised by a
bracketed span followed by an opening parenthesis or bracket, which covers an inline link, an image
and a collapsed reference link, and misses the shortcut form: a bracketed label alone, which
markdown resolves against a link reference definition elsewhere in the document.

The shortcut form disagrees with a renderer the same way the others do. A renderer uses the label's
text and this rule also drops the brackets, which happens to agree, but the rendered text is the
label while the source is the label plus its brackets, and a label containing markdown of its own
reopens the question. Recognising it needs the document's link reference definitions rather than
the heading alone, which nothing in this check reads.

It was unreachable in this tree, measured rather than assumed: a review of all 404 markdown files
on the day this was written found zero link reference definitions and zero headings with a
bracketed span that is not already an inline link.

Two ways to close it: collect each document's link reference definitions in one pass and refuse a
heading whose bracketed label names one, or refuse a bare bracketed span in a heading outright,
which costs one regular expression and no second pass but forbids a literal bracket in a heading.

## History

- 2026-08-18: Opened by the close of [292](292-slug-rule-approximates-a-renderer.md), which checked
  the slug rule against a renderer and found this remainder beside the six shapes it refused.
- 2026-08-20: Fixed by the wider of the two options, the one this entry called probably better. The
  detector no longer requires an opening parenthesis or bracket after a label, so a bracketed span
  in a heading is refused whatever follows it. Re-measured first and the margin held: 431 markdown
  files, 2149 ATX headings, zero link reference definitions and zero headings with a bracket at
  all, so nothing in the tree had to be rewritten. The refusal message changed with the rule, and
  the suite asserts it on the shortcut form, the collapsed form and a bracketed aside nobody meant
  as a link. Proved able to fail against the old detector, which passes two of those three, and on
  a heading planted in a real runbook. The reasoning is ADR-0039 decision 10. The cost this entry
  named, a heading that means its brackets literally, opens as
  [R-334](334-a-heading-whose-brackets-are-prose.md).
