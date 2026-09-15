# A double backtick code span is torn apart before the inline shapes are looked for

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)
**Verified:** 2026-09-15
**Trigger:** the first heading quoting something in a double backtick code span, which
`backlogcheck` refuses whenever what is quoted holds brackets, an angle-bracket tag or an entity
reference, printing a remedy the author has already followed.

Opened 2026-09-15 by the close of [R-344](344-a-remedy-that-repeats-the-heading.md), which made the
bracketed refusal name the code span as the way a heading carries a literal pair of brackets.
`CODE_SPAN` in `scripts/headingshapes.py` is `` `[^`]*` ``, which reads a span delimited by one
backtick. A span delimited by two is stripped as two empty spans, its opening and closing pairs,
and what was inside them is left in the text the five inline shapes are then looked for. So the
shapes see markup a renderer never renders. Running `problems()` over four headings shows it:

```markdown
## Array index ``a[0]`` here          refused: brackets a span
## The tag ``<kbd>`` spelled out      refused: carries angle-bracket markup
## The entity ``&amp;`` spelled out   refused: carries an entity reference
## A closed run ``##`` quoted         accepted
```

The single backtick spelling of each of the first three is accepted. The fourth passes because the
closing-hash rule reads the raw line and needs the hashes at its end.

**Why it matters more since the remedy changed.** The bracketed refusal now tells an author to
quote the brackets in a code span. An author who writes the double backtick spelling, which is what
CommonMark requires as soon as the quoted text itself holds a backtick, is told to do the thing
they did, which is the shape the remedy was reworded to stop printing.

**What would close it.** Either a `CODE_SPAN` that reads a run of backticks and its matching run,
which is the CommonMark rule and costs one pattern, or a decision that the single backtick spelling
is the house style and a refused double backtick heading is rewritten to it, in which case the
remedy should say so. Nothing in the tree forces the choice yet: a sweep on 2026-09-15 over the 772
markdown files `treewalk` walks found no heading refused by any of the six shapes, and none quoting
anything in a double backtick span.

## Trail

- 2026-09-15: opened by the close of [R-344](344-a-remedy-that-repeats-the-heading.md), whose new
  remedy names a construct the rule reads in one of its two spellings.
