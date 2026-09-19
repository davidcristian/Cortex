# The substitution reader refuses a brace compose reads as text

**Status:** open, fix when it bites
**Area:** repo-gates
**Trigger:** a commit under `docker/` replaces a literal JSON value in a compose file with a spend,
which is the change that would next want the JSON as that spend's default. Checkable with
`git log -p -- 'docker/*.yml'`, reading for a removed line whose value opens with `{` and an added
one spending a variable in its place; today the JSON values are the subagent roster's endpoint list
in `docker/docker-compose.subagents-roster.yml` and the two `enable_thinking` template arguments,
all literal
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-checks.md)
**Verified:** 2026-09-19

Opened 2026-09-19 by the change that made `scripts/composedefaults.py` quote a spend carrying a `{`
whole, recorded in the [ADR-0026 addendum on quoting a nested spend
whole](../../adr/ADR-0026-prose-style-checks.md).

The reader raises `SubstitutionReadError` on any spend whose body carries a `{`, and since that
change a bare `{` in an argument gets its own fault: `${A:-{x}} carries a brace in its argument,
which this reader was not taught`. Compose reads the form. Measured with `docker compose config` on
v2.39.1, `${A:-{x}}tail` gives `{x}tail` with nothing set and `outertail` with `A=outer`, so the
spend ends at the `}` balancing its opening and its default is `{x}`; `${A:-{x}`, which no brace
balances, gives `{x`, ending at the first `}`. Before that change the reader called the bare brace
a nested substitution, so the refusal was never a decision about this form: it fell out of the
nesting check.

Unlike a nested default, a brace-bearing default is one value, so `defaultcheck.py` could compare
it as text the way it compares a path. The case that would want it is a JSON value made
operator-settable with the JSON kept as its default.

**The fix.** In `_braced`, when the body carries a `{` but the balanced extent (`_spend_extent`)
carries no `${`, read the spend to that extent and take the argument as the text between the
operator and the balancing `}`, falling back to the first `}` as compose does. A `${` inside stays
the nested refusal owned by
[R-502](502-the-substitution-reader-refuses-a-nesting-compose-expands.md). Widen the measurement
first to a JSON object nested two deep, `${A:-{"k": {"j": 1}}}`, and to a replacement operator, and
confirm `bindcheck.py`, whose own pattern reduces a bind source, is unaffected.

## Trail

- 2026-09-19: opened by the change that quotes a brace-bearing spend whole, whose [ADR-0026
  addendum](../../adr/ADR-0026-prose-style-checks.md)
  holds the measurement.
