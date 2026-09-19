# A note written after a compose value is read as another use of the variable it names

**Status:** declined 2026-08-23
**Area:** repo-checks
**Origin:** [ADR-0063](../../adr/ADR-0063-compose-checks.md)

`scripts/composedefaults.py` skips a whole-line comment, because compose expands nothing in one,
so a default written there is prose. It does not detect a trailing `#`. That was a decision, not
an oversight: the reader walks characters and has no model of YAML quoting, so it cannot tell a
comment marker from a `#` inside a quoted scalar, and reading the text either way is the choice
that fails rather than guesses. A note reading
`source: "${CORTEX_MODELS_DIR:-./models}"  # was ${CORTEX_MODELS_DIR:-./cache}` makes the check
fail, naming line 183 twice, while the same sentence on its own line above leaves it passing.

No compose file in the tree has that shape, so the strictness costs nothing today, and the remedy
is one line long: move the note above the value.

## History

- 2026-08-22: opened by the close of
  [R-355](355-one-variable-several-defaults-no-declaration.md), which added
  `scripts/defaultcheck.py`, measured this behaviour in both directions, and recorded it as the
  one strictness that close deliberately accepted.
- 2026-08-23: declined, on three measurements. The strictness is a false report rather than a
  conservative reading: `docker compose config` accepts an unset `${VAR:?...}` written as a
  whole-line comment and as a trailing one, refuses the same form in a live value, and names a
  path into the parsed document when it does, so interpolation runs over what a YAML parse
  produced and nothing in a note is ever expanded. The remedy this entry proposed makes the check
  fail over the tree it protects: implemented exactly as described and run over the ten compose
  files, it refuses five lines, the three block scalars in `docker-compose.tools.yml` and
  `docker-compose.subagents-roster.yml` and two lines inside the roster's folded scalar with an
  odd number of double quotes. A block scalar cannot be skipped either, its content being
  interpolated like any other value, so a correct reader needs block tracking with indentation,
  which is a YAML parser in a project that declares no dependencies. The asymmetry decides it: a
  note read as a use is reported and is one line from its remedy, while a `#` wrongly read as a
  marker drops every later use from the comparison and reports nothing, which is the failure this
  check exists to remove. `scripts/composedefaults.py` and
  [docs/modules/repo-checks.md](../../modules/repo-checks.md) now say the reading is settled
  rather than deferred, and both lose the claim that compose expands the raw text before YAML sees
  it. One narrower task opens, the fault message that names one line twice and never mentions the
  remedy ([R-391](391-a-fault-that-names-one-line-twice.md)). Argued in
  [ADR-0063](../../adr/ADR-0063-compose-checks.md), decision 8.
