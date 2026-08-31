# Nothing holds a cap sized on the answer to a tier whose trace is bounded

**Status:** open, a seam or port change comes first
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-27 by the close of
[R-458](458-the-ports-thinking-switch-is-conditional.md), which made the failure visible at runtime
and left it possible to write.

The pairing rule this repo keeps is that a `max_tokens` sized on the wanted answer is only safe
against a **bounded trace**, because a reasoning model spends its budget thinking first. Four
shipped bounds pair a cap with `thinking=False` and take that as the bound. Measured, that switch is
a request the deployment may not honour, so the rule's precondition can be false at runtime while
every gate is green, and the fifth caller to write such a pair will write it exactly the same way.

What now exists is the report, not the hold: `drain_text` logs the model and the characters it
dropped when a request that asked for no thinking is answered with a trace, and
`test_thinking_switch_live.py` answers the question per shape for a deployment that thinks to ask.
Both are after the fact.

**Why it was left.** A gate would need a fact the core is built not to carry. Whether a
tier's trace is bounded is a property of that tier's argv (`--reasoning-budget`), which lives in the
model host's config and in two compose files, and the core reaches inference through a port that
deliberately says nothing about how the server was started. Giving the port a
"the trace is bounded here" capability is the obvious move and the wrong one on today's evidence:
llama.cpp offers no way to ask, so the value would be a deployment's own claim about itself, which
is a setting that can be wrong in the other direction.

**What would close it.** Something that catches the pairing at the point it is written rather than
the point it fires. Three candidates, none costed: a constructor-level rule that a cap-carrying
`GenerationBounds` on a schema-carrying request is a shape that needs a named justification; a
`crosscheck` entry tying every shipped bounds constant to the tier its caller runs on and that
tier's own budget flag; or the accepting answer, that a cap on any tier is safe once the trace is
bounded at the engine and the repair is a documented deployment default (`CORTEX_REASONING_BUDGET`
non-negative on every tier a bound caller uses) rather than a check. The third is the cheapest and
should be argued against before the first two are built.
