# The substitution reader refuses a brace compose reads as text

**Status:** open, waiting for its trigger
**Trigger:** a commit under `docker/` replaces a literal JSON value in a compose file with a
variable substitution, which is the change that would next want the JSON as that substitution's
default. Checkable with `git log -p -- 'docker/*.yml'`, reading for a removed line whose value opens
with `{` and an added one using a variable in its place; today the JSON values are the subagent
roster's endpoint list in `docker/docker-compose.subagents-roster.yml` and the two
`enable_thinking` template arguments, all literal
**Area:** repo-checks
**Origin:** [ADR-0063](../../adr/ADR-0063-compose-checks.md)
**Verified:** 2026-09-19

`scripts/composedefaults.py` raises `SubstitutionReadError` on any substitution whose body contains
a `{`, and a bare `{` in an argument now gets its own message: `${A:-{x}} carries a brace in its
argument, which this reader was not taught`. Compose reads the form. Measured with
`docker compose config` on v2.39.1, `${A:-{x}}tail` gives `{x}tail` with nothing set and `outertail`
with `A=outer`, so the substitution ends at the `}` balancing its opening and its default is `{x}`;
`${A:-{x}`, which no brace balances, gives `{x`, ending at the first `}`. Before the message was
added the reader called the bare brace a nested substitution, so the refusal was never a decision
about this form: it fell out of the nesting check.

Unlike a nested default, a brace-bearing default is one value, so `defaultcheck.py` could compare it
as text the way it compares a path. The case that would want that is a JSON value made
operator-settable with the JSON kept as its default.

**The fix.** In `_braced`, when the body contains a `{` but the balanced extent (`_spend_extent`)
contains no `${`, read the substitution to that extent and take the argument as the text between the
operator and the balancing `}`, falling back to the first `}` as compose does. A `${` inside stays
the nested refusal owned by
[R-502](502-the-substitution-reader-refuses-a-nesting-compose-expands.md). Widen the measurement
first to a JSON object nested two deep, `${A:-{"k": {"j": 1}}}`, and to a replacement operator, and
confirm `bindcheck.py`, whose own pattern reduces a bind source, is unaffected.

## History

- 2026-09-19: opened by the change that made the reader quote a brace-bearing substitution whole,
  recorded in [ADR-0063](../../adr/ADR-0063-compose-checks.md) decision 9; the measurement is in
  [compose interpolation](../../readings/compose-interpolation.md).
