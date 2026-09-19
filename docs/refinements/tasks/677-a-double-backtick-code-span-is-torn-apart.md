# A double backtick code span is torn apart before the inline shapes are looked for

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)
**Verified:** 2026-09-19
**Trigger:** the first heading quoting something in a double backtick code span, which
`backlogcheck` refuses whenever what is quoted has brackets, an angle-bracket tag or an entity
reference. For brackets the printed advice is the code span the author already wrote; for a tag or
an entity it is the shared advice, which tells the author to drop the quote and write plain text.

`CODE_SPAN` in `scripts/headingshapes.py` is `` `[^`]*` ``, which reads a span delimited by one
backtick. A span delimited by two is stripped as two empty spans, its opening and closing pairs, and
what was inside them is left in the text the five inline shapes are then looked for. So the shapes
see markup a renderer never renders. Running `problems()` over four headings shows it:

```markdown
## Array index ``a[0]`` here          refused: brackets a span
## The tag ``<kbd>`` spelled out      refused: carries angle-bracket markup
## The entity ``&amp;`` spelled out   refused: carries an entity reference
## A closed run ``##`` quoted         accepted
```

The single backtick form of each of the first three is accepted. The fourth passes because the
closing-hash rule reads the raw line and needs the hashes at its end.

**Why it matters more since the advice changed.** The bracketed refusal now tells an author to quote
the brackets in a code span. An author who writes the double backtick form, which is what CommonMark
requires as soon as the quoted text itself has a backtick, is told to do the thing they did.

**What would close it.** Either a `CODE_SPAN` that reads a run of backticks and its matching run,
which is the CommonMark rule and costs one pattern, or a decision that the single backtick form is
the house style and a refused double backtick heading is rewritten to it, in which case the advice
should say so.

## History

- 2026-09-15: opened by the close of [R-344](344-a-remedy-that-repeats-the-heading.md), which made
  the bracketed refusal name the code span as the way a heading can have a literal pair of brackets,
  a construct the rule reads in only one of its two forms. A pass over the 772 markdown files
  `treewalk` walks found no heading refused by any of the six shapes, and none quoting anything in a
  double backtick span.
- 2026-09-19: the trigger has not fired, and its account of the advice was half right. The four
  headings above were run through `problems()` again and reproduce exactly: the first three refused,
  the closed run accepted. The advice each refusal prints differs, which the trigger did not say.
  Only the bracketed refusal has its own, and it names the code span the author already wrote. The
  tag and entity refusals print the shared one, `write it as plain text under leading hashes`, which
  is wrong advice for a quote rather than a repeat of what was done. The trigger now says both. Over
  the 781 markdown files git tracks, no heading has a double backtick, and `problems()` refuses none
  of their headings.
