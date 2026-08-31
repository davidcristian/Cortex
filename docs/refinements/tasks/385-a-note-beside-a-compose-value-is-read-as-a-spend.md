# A note written after a compose value is read as a spend of the variable it names

**Status:** declined 2026-08-23
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-08-22 by the close of
[R-355](355-one-variable-several-defaults-no-declaration.md), which landed
`scripts/defaultcheck.py` and recorded this as the one strictness that close deliberately bought.

`scripts/composedefaults.py` skips a **whole-line** comment, compose expanding nothing in one, so a
default written there is prose and belongs to the cross-language scan rather than to this gate. It
does not detect a **trailing** `#`, and that is written down as a decision rather than an
oversight: the reader is a character walk with no model of YAML quoting, so it does not distinguish
a comment marker from the `#` in a quoted scalar, and reading the text either way is the
fail-closed choice. The measured consequence is in that ADR's proof table. A note reading
`source: "${CORTEX_MODELS_DIR:-./models}"  # was ${CORTEX_MODELS_DIR:-./cache}` makes the gate
fail, naming line 183 twice, while the same sentence on its own line above leaves it green.

**Why it was left.** No compose line in the tree carries that shape, so the strictness costs
nothing today, and the remedy when somebody hits it is one line long: move the note above the value.
The alternative was a quoting model written against text this repo does not contain, and such a
transform can be wrong without reporting anything, where a refusal at least reports. It is the same
argument `headingshapes.py` makes for refusing six heading shapes rather than emulating a renderer.

**What would close it.** Teach the reader enough of YAML's scalar grammar to find a real comment
marker: a `#` is one when it opens a line, or when it follows whitespace outside a quoted scalar,
which means tracking single and double quotes across the line and the backslash escape inside the
double-quoted form. Then skip from that marker to the end of the line and read no substitution past
it. The cost is a reader that is no longer a plain character walk, and it needs its own refusals
(an unterminated quote, a block scalar) rather than a guess. Weigh that against the alternative of
leaving it: it costs nothing until a compose file needs a note beside a value, and a repo-wide gate
that is strict in a direction the tree has no instances of costs little. Whichever way it goes,
the reader's docstring and the module contract already state the current behaviour and would have
to move with it.

## Trail

- 2026-08-22: opened by the close of
  [R-355](355-one-variable-several-defaults-no-declaration.md), which measured the behaviour in
  both directions and recorded it as the deferral that close opens.
- 2026-08-23: declined, and three measurements say why. **The strictness is a false positive rather
  than a conservative reading**: `docker compose config` accepts an unset `${VAR:?...}` written as
  a whole-line comment and as a trailing one, refuses the same form in a live value, and names a
  path into the parsed document when it does, so interpolation runs over what a YAML parse
  produced and nothing in a note is ever spent. **The remedy as written here makes the gate fail
  over the tree it protects**: implemented exactly as this entry describes it and run over the ten
  compose files, it refuses five lines, the three block scalars in `docker-compose.tools.yml` and
  `docker-compose.subagents-roster.yml` and two lines inside the roster's folded scalar carrying an
  odd number of double quotes. **And a block scalar cannot be skipped either**, its content being
  interpolated like any other value, so a correct reader needs block tracking with indentation,
  which is a YAML parser in a project that declares no dependencies. The asymmetry decides it: a
  note read as a spend is reported and is one line from its remedy, while a `#` wrongly read as a
  marker drops every later spend from the comparison without reporting anything, which is the
  failure the gate exists to remove. `scripts/composedefaults.py` and
  [docs/modules/repo-gates.md](../../modules/repo-gates.md)
  now say the reading is settled rather than deferred, and both lose the claim that compose expands
  the raw text before YAML sees it. One narrower task opens, the fault message that names one line
  twice and never mentions the remedy ([R-391](391-a-fault-that-names-one-line-twice.md)). Argued
  in the ADR-0026 trailing-note addendum.
