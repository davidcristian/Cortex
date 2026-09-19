# A heading whose brackets are prose has no way to say so

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)
**Verified:** 2026-09-19
**Trigger:** the first heading somebody wants to write with a pair of brackets in prose, which the
heading rule refuses whatever follows them and which a code span cannot express, monospace being
wrong for prose.

`scripts/headingshapes.py` refuses a bracketed span in a heading with or without a target after it.
That reaches the shortcut reference form, which has no marker of its own, and it also reaches a
pair of brackets nobody meant as a link. The second half is the price, accepted when the rule was
written because no heading in the tree uses one: a review of all 431 markdown files found zero
headings with a bracket at all.

No exemption marker was built. `dashcheck.py` has one, a line with `dashcheck: allow` plus a
reason. The same shape would work here and was left unbuilt on purpose: an exemption for something
nobody has written is machinery aimed at a hypothetical, and an inline marker in a heading is
itself text a renderer has to drop, so where the marker goes is part of the question.

Three ways to close it, to be decided against the heading that asks: rewrite that heading (the
answer so far), an escape the rule accepts (CommonMark already reads `\[` as a literal bracket, and
this rule could drop the backslash the way it drops a backtick, which costs one substitution and no
exemption vocabulary), or a per-line allow marker with a reason, the `dashcheck.py` idiom. The
escape is the interesting one, since it makes the source say what it means.

## History

- 2026-08-20: Opened by the close of [R-307](307-shortcut-reference-link-in-a-heading.md), whose
  wider refusal covers a case it does not aim at.
- 2026-09-10: The trigger has not fired. The survey this entry rests on was re-run over today's
  tree, 725 tracked markdown files against the 431 it was written over, and no heading has a
  bracket at all, in or out of a code span. `BRACKETED` in `scripts/headingshapes.py` still refuses
  a bracketed span with or without a target after it.
- 2026-09-15: This entry is narrower than its old title said, which running the reader showed, and
  the title now says so, the file having been called `a-heading-that-means-its-brackets` until
  today. A heading can have a literal pair of brackets now, in a code span: `CODE_SPAN` is stripped
  before `BRACKETED` is looked for, so ``## Array index `a[0]` `` is accepted, and it produces the
  same slug on both sides because the backticks come off on both. So the option list above gains a
  fourth entry that needs no decision, and what stays open is a pair of brackets in prose, where
  monospace is the wrong rendering. The survey was re-run over the 772 tracked markdown files, up
  from 725 on 2026-09-10, and still finds no heading with a bracket at all. The refusal's remedy
  names the code span from today, which is the close of
  [R-344](344-a-remedy-that-repeats-the-heading.md), and it names rewriting for the prose case this
  entry keeps.
- 2026-09-19: The trigger has not fired. Over the 781 markdown files git tracks today, no heading
  has a bracket at all, in a code span or out of one, and `problems()` refuses none of their
  headings. Running `problems()` again confirms the account above: a heading quoting `a[0]` in a
  single backtick code span is accepted, a pair of brackets in prose is refused with the code span
  remedy, and so is the backslash escape, `\[prose\]`, because `BRACKETED` in
  `scripts/headingshapes.py` still matches the bracket after the backslash. The escape named above
  is therefore still unbuilt rather than already accepted.
