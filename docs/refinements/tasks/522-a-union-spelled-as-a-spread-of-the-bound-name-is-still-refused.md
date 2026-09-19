# A union written as a spread of the bound name is still refused

**Status:** declined 2026-09-15
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

`scripts/logfields.py` follows a bare name, and a name unioned with a mapping written out at the
call as `extra | {"shortfall": reading.shortfall}`, to one binding above the call. The other way to
write the same union, a mapping at the call that spreads the bound name into itself, prints the same
line and is refused. Until 2026-09-15 `_literal` reported a spread as a field name that is not a
plain string. Reading it would mean treating a `**name` entry whose name meets the four conditions
as the bound mapping's keys and refusing every other spread, which is one more case in `_named` and
a fixture per branch. Not built, because the brain writes the `|` form and nothing else.

## History

- 2026-09-02: opened by the close of
  [R-516](516-a-field-list-composed-above-its-call-cannot-be-quoted.md), whose mutation table
  measures the `|` union read and says nothing about a spread.
- 2026-09-04: checked and left open. The brain's log calls attach 94 `extra=` expressions: 85 are a
  mapping written out at the call, six are a bare name, one is the `|` union at
  `cortex_core/brain_phase.py:210`, and two are a call, `_pairing(subagents, tools)` at
  `cortex_orchestrator/bounds.py:129` and line 144, which this reader refuses. None of the 85 has a
  `**` entry.
- 2026-09-07: checked again and left open. The same census as 2026-09-04, except that the formatter
  has moved the two `_pairing` calls to lines 131 and 144.
- 2026-09-13: checked again and left open. The census has grown by two calls at a shape this entry
  does not describe: 96 in all, 85 a mapping written out at the call, six a bare name, one the `|`
  union, and four a call rather than two. The two new ones are `bounds.pairing_fields(...)` at
  `cortex_core/residency_watch.py:199` and `cortex_orchestrator/swap_builders.py:209`. None of the
  85 mappings has a `**` entry.
- 2026-09-15: declined, with the cost of the refusal paid down instead (ADR-0045 decision 9). The
  census reproduces a fifth time and the brain still writes no spread: 96 `extra=` expressions, 85 a
  mapping written out at the call, six a bare name, one the `|` union, four a call, and no `**`
  entry among the 85. Two lines moved, the `|` union from `brain_phase.py:210` to 245 and one
  `_pairing` call in `bounds.py` from 134 to 132. Running the spread through `logfields.attached`
  confirms the refusal at the failure this entry names. What the entry asked for is declined on its
  own reason rather than on soundness: reading a `**name` entry over a name meeting the four
  conditions would agree with the `|` union on every line, since the keys are the same and fields
  are sorted before they are compared, and the case would still be written against no call in the
  tree. What the refusal actually cost was one message, and that is now paid: `_literal` names
  `extra | {...}` as the union this reader follows, so the day somebody writes the spread costs them
  a one-line edit at the call. The failure is raised wherever a spread sits and reports the
  mapping's own line, which the suite covers in three cases.
