# A union spelled as a spread of the bound name is still refused

**Status:** declined 2026-09-15
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-09-02 by the close of
[R-516](516-a-field-list-composed-above-its-call-cannot-be-quoted.md), which taught
`scripts/logfields.py` to follow a bare name, and a name unioned with a mapping written out at the
call as `extra | {"shortfall": reading.shortfall}`, to one binding above the call.

The other spelling of the same union, a mapping written out at the call that spreads the bound name
into itself, prints the same line and is refused. Until 2026-09-15 `_literal` reported a spread as
a field name that is not a plain string, which is what it reported before this reader existed and
is true of a spread of any name the reader would not follow. Reading it would mean treating a
`**name` entry whose name meets the four conditions as the bound mapping's keys and refusing every
other spread, which is one more case in `_named` and a fixture per branch. Not built, because the
brain writes the `|` spelling and nothing else, and a reader case written against no example is a
guess about a shape nobody has asked for. When one arrives, the fault names its line and names
`extra | {...}` as the union this reader follows.

## Trail

- 2026-09-02: opened by the close of
  [R-516](516-a-field-list-composed-above-its-call-cannot-be-quoted.md), whose mutation table
  measures the `|` union read and says nothing about a spread.
- 2026-09-04: checked and left open. The trigger has not fired. The brain's log calls attach 94
  `extra=` expressions: 85 are a mapping written out at the call, six are a bare name, one is the
  `|` union at `cortex_core/brain_phase.py:210`, and two are a call, `_pairing(subagents, tools)`
  at `cortex_orchestrator/bounds.py:129` and line 144, which this reader refuses as neither a
  mapping written out nor a name bound to one. None of the 85 carries a `**` entry, so no mapping
  in the brain spreads a name into itself and the case this entry describes still has no example to
  be written against.
- 2026-09-07: re-checked and left open. The trigger has not fired. Reading the `extra=` of every
  log call in the brain's source and sorting by the shape of the expression gives the same census
  as 2026-09-04: 94 in all, 85 a mapping written out at the call, six a bare name, one the `|`
  union at `cortex_core/brain_phase.py:210`, and two a call, `_pairing(subagents, tools)` in
  `cortex_orchestrator/bounds.py`, which the formatter has moved to lines 131 and 144 from the 129
  and 144 recorded before. None of the 85 mappings carries a `**` entry, so the shape this entry
  describes still has no example in the brain and a reader case for it would still be written
  against no call.
- 2026-09-13: re-checked and left open. The trigger has not fired, and the census has grown by
  two calls at the shape this entry does not describe. Reading the `extra=` of every log call in
  the brain's source and sorting by the shape of the expression gives 96 in all, where 94 were
  read before: 85 a mapping written out at the call, six a bare name, one the `|` union at
  `cortex_core/brain_phase.py:210`, and four a call rather than the two recorded before. The two
  new ones are `bounds.pairing_fields(...)` at `cortex_core/residency_watch.py:199` and at
  `cortex_orchestrator/swap_builders.py:209`, and the two already recorded are `_pairing(...)` in
  `cortex_orchestrator/bounds.py`, which the formatter has moved to lines 134 and 147 from the 131
  and 144 recorded before. None of the 85 mappings carries a `**` entry, so the shape this entry
  describes still has no example in the brain and a reader case for it would still be written
  against no call.
- 2026-09-15: **declined**, with the cost of the refusal paid down instead (ADR-0009
  spread-refusal addendum). The census reproduces a fifth time and the brain still writes no
  spread: 96 `extra=` expressions, 85 a mapping written out at the call, six a bare name, one the
  `|` union, four a call, and no `**` entry among the 85. Two lines moved, the `|` union from
  `brain_phase.py:210` to 245 and one `_pairing` call in `bounds.py` from 134 to 132. Running the
  spread through `logfields.attached` confirms the refusal this entry describes, at the fault the
  entry names. What the entry asked for is declined on its own reason rather than on soundness:
  reading a `**name` entry over a name meeting the four conditions would agree with the `|` union
  on every line, since the keys are the same and fields are sorted before they are compared, and
  the case would still be written against no call in the tree. What the refusal actually cost was
  one message, and that is now spent: `_literal` names `extra | {...}` as the union this reader
  follows, so the day somebody writes the spread costs them a one-line edit at the call rather
  than a reading of `logfields.py`. The fault is raised wherever a spread sits and reports the
  mapping's own line, which the suite pins in three cases.
