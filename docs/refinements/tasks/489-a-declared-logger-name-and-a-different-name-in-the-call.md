# A declared logger name and a different name in the call

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-08-28 by the close of
[R-488](488-a-declared-logger-name-is-never-held-to-the-call-that-passes-it.md), which held the
half of that hole a rule about one module's own text can reach.

A module may no longer spell one logger name twice: `scripts/logcalls.py` refuses a literal
`getLogger` argument that the same module's top level also binds. What it cannot see is a module
binding `_LOGGER_NAME = "cortex.tools.audit"` and calling `getLogger("cortex.tools.other")`, which
is two names rather than one spelled twice. The constant registry then ties the runbooks, the
docstring and the suite to the declaration while the brain writes the other name, and the gate is
green unless some document happens to quote a rendered sample of that trail, which is what would
make `samplecheck.py` ask for a logger no module declares.

**Why it was left.** The close weighed both wider rules and declined both. "A module binding
`_LOGGER_NAME` must pass it" makes the gate tree spell that identifier, which is a third spelling of
exactly the kind of value this repo would then want tied to the two sinks, and a convention a gate
runs over is the shape [R-472](472-the-membership-prefix-is-a-convention-nothing-enforces.md) is
already open about. Teaching the constant scan what a logger is would put a subject inside the
registry's data, where every other entry is a value and two places that spell it.

**What would close it.** Weigh whether the gap is worth a rule at all before building one: reaching
this state from today's tree takes an edit that replaces an identifier with a different literal,
which is not what a refactor does by accident, where the redundancy the close blocked is exactly
what inlining a constant used once produces. If it is worth holding, the cheapest honest shape is
probably to let the registry mark which of its sites is a logger name and have the sample gate read
that one fact, since the registry already knows which declarations documents restate, and a site
that says what it is costs no convention.

## Trail

- 2026-08-28: opened by the close of
  [R-488](488-a-declared-logger-name-is-never-held-to-the-call-that-passes-it.md), whose mutation
  table holds one name spelled twice on both sinks and never asks which name the call passed.
