# The defaults gate counts a file it could not read as a variable

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)
**Verified:** 2026-09-19

Opened 2026-09-19 by the change that made `scripts/composedefaults.py` quote a spend carrying a `{`
whole, recorded in the [ADR-0026 addendum on quoting a nested spend
whole](../../adr/ADR-0026-prose-style-gates.md).

`defaultcheck.main` ends a failing run with `{n} compose variable(s) do not carry one default`,
where `n` counts every `Fault`. A `Fault` is one of two things (its own docstring says so): a
variable whose spends disagree, or a compose file `_read` could not read, whose subject is the
file's path. Measured today with `uv run python defaultcheck.py --root <scratch>` over one file
spelling a nested spend and nothing else: the run printed `1 compose variable(s) do not carry one
default` above a fault naming `docker-compose.yml`, which is a file and carries no default at all.
The remedy the line then gives, to give every spend of one variable the same default, is no remedy
for a refused form.

**The fix.** Keep the two kinds apart where they are made: `check` already holds the walk's read
faults (`Walk.faults`) separately from the disagreements it adds, so return them in two fields of
`Scan`, and have `main` print one summary sentence per kind that occurred, a count of files the
reader refused with the remedy of rewriting the refused form, and the existing sentence over
variables only. Assert each summary whole in `tests/test_defaultcheck.py`, including a run carrying
both kinds.

## Trail

- 2026-09-19: opened by the change that quotes a brace-bearing spend whole, whose [ADR-0026
  addendum](../../adr/ADR-0026-prose-style-gates.md)
  records the run that showed it.
