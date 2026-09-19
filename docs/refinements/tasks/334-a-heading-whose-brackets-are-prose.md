# A heading whose brackets are prose has no way to say so

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)
**Verified:** 2026-09-19
**Trigger:** the first heading somebody wants to write with a pair of brackets in prose, which the shape rule refuses whatever follows them and which a code span cannot carry, monospace being wrong for prose.

Opened 2026-08-20 by the close of [R-307](307-shortcut-reference-link-in-a-heading.md), which made
`scripts/headingshapes.py` refuse a bracketed span in a heading with or without a target after it.
That reaches the shortcut reference form, which carries no mark of its own, and it reaches a pair of
brackets nobody meant as a link along with it. The second half is the price, named when the rule
landed and accepted on the ground that no heading in the tree spends one: a sweep of all 431
markdown files found zero headings carrying a bracket at all.

**Why no escape hatch was built.** `dashcheck.py` has one, a line carrying `dashcheck: allow` plus a
reason, for a dash that means rather than punctuates. The same shape would work here and was left
unbuilt on purpose. An exemption for a shape nobody has written is machinery aimed at a
hypothetical, and the exemption a real heading asks for is easier to design than the one imagined
for it: an inline marker in a heading is itself text a renderer has to drop, so where the marker
goes is part of the question rather than a detail after it.

**What would close it.** Decide, against the heading that asked, between three: rewriting that
heading (the answer for every heading so far), an escape the rule honours (CommonMark already reads
`\[` as a literal bracket, and this rule could drop the backslash the way it drops a backtick, which
costs one substitution and no exemption vocabulary), or a per-line allow marker with a reason, which
is the `dashcheck.py` idiom and the loudest of the three. The escape is the interesting one, since
it makes the source say what it means instead of adding an exemption the gate has to honour.

## Trail

- 2026-08-20: opened by the close of [R-307](307-shortcut-reference-link-in-a-heading.md), whose
  wider refusal bans a shape it does not aim at, and by the same argument that entry used for
  refusing outright rather than collecting each document's link reference definitions.
- 2026-09-10: the trigger has not fired. The sweep this entry rests on was re-run over today's
  tree, 725 tracked markdown files against the 431 it was written over, and no heading in any of
  them carries a bracket at all, in or out of a code span. `BRACKETED` in
  `scripts/headingshapes.py` still refuses a bracketed span with or without a target after it, so
  the price named when the rule landed is still a price nobody has paid.
- 2026-09-15: this entry is narrower than its old title said, which running the reader showed, and
  the title now says so, the file having been called `a-heading-that-means-its-brackets` until
  today. A heading can carry a literal pair of brackets now, in a code span: `CODE_SPAN` is
  stripped before `BRACKETED` is looked for, so ``## Array index `a[0]` `` is accepted, and it
  slugs the same on both sides because the backticks come off on both. So the option list above
  gains a fourth entry that needs no decision, and what stays open is a pair of brackets in prose,
  where monospace is the wrong rendering. The sweep was re-run over the 772 tracked markdown files,
  up from the 725 of 2026-09-10, and still finds no heading carrying a bracket at all. The
  refusal's remedy names the code span from today, which is the close of
  [R-344](344-a-remedy-that-repeats-the-heading.md), and it names rewriting for the prose case this
  entry holds.
- 2026-09-19: the trigger has not fired. Over the 781 markdown files git tracks today, no heading
  carries a bracket at all, in a code span or out of one, and `problems()` refuses none of their
  headings. Running `problems()` again confirms the account above: a heading quoting `a[0]` in a single
  backtick code span is accepted, a pair of brackets in prose is refused with the code span remedy,
  and so is the backslash escape, `\[prose\]`, because `BRACKETED` in `scripts/headingshapes.py`
  still matches the bracket after the backslash. The escape named under what would close it is
  therefore still unbuilt rather than already honoured.
