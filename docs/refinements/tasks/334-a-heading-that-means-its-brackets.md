# A heading that means its brackets literally has no way to say so

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)
**Trigger:** the first heading somebody wants to write with a literal pair of brackets in it, which the shape rule now refuses whatever follows them.

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
