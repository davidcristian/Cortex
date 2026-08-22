# A note written after a compose value is read as a spend of the variable it names

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-08-22 by the close of
[R-355](355-one-variable-several-defaults-no-declaration.md), which landed
`scripts/defaultcheck.py` and recorded this as the one strictness that close deliberately bought.

`scripts/composedefaults.py` skips a **whole-line** comment, compose expanding nothing in one, so a
default written there is prose and belongs to the cross-language scan rather than to this gate. It
does not detect a **trailing** `#`, and that is written down as a decision rather than an
oversight: the reader is a character walk with no model of YAML quoting, so it cannot tell a
comment marker from the `#` in a quoted scalar, and reading the text either way is the fail-closed
side of not knowing. The measured consequence is in that ADR's proof table. A note reading
`source: "${CORTEX_MODELS_DIR:-./models}"  # was ${CORTEX_MODELS_DIR:-./cache}` reddens the gate,
naming line 183 twice, while the same sentence on its own line above leaves it green.

**Why it was left.** No compose line in the tree carries that shape, so the strictness costs
nothing today, and the remedy when somebody hits it is one line long: move the note above the value.
The alternative was a quoting model written against text this repo does not contain, which is the
kind of transform whose wrongness is silent, where the refusal is loud. The same argument
`headingshapes.py` makes for refusing six heading shapes rather than emulating a renderer.

**What would close it.** Teach the reader enough of YAML's scalar grammar to find a real comment
marker: a `#` is one when it opens a line, or when it follows whitespace outside a quoted scalar,
which means tracking single and double quotes across the line and the backslash escape inside the
double-quoted form. Then skip from that marker to the end of the line and read no substitution past
it. The cost is a reader that is no longer a plain character walk, and it wants its own refusals
(an unterminated quote, a block scalar) rather than a guess. Weigh that against the alternative of
leaving it: it costs nothing until a compose file wants a note beside a value, and a repo-wide gate
that is strict in a direction with no instances is a cheap kind of wrong. Whichever way it goes,
the reader's docstring and the module contract already state the current behaviour and would have
to move with it.

## Trail

- 2026-08-22: opened by the close of
  [R-355](355-one-variable-several-defaults-no-declaration.md), which measured the behaviour in
  both directions and recorded it as the deferral that close opens.
