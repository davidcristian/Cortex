# A registered binding handed at a wrapped call has no one-line needle

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** registering a message binding whose call the formatter wraps, which is what
`cortex_orchestrator/abandon.py` and the no-reading call in `cortex_core/brain_phase.py` would be.

Opened 2026-09-02 by the close of
[R-504](504-a-declared-message-and-a-different-word-in-the-call.md), which holds a registered
message binding to the call handed it by a mention of the call rendering the identifier,
`_logger.info({name},`, and requires such a mention of every registry site a brain log call is
handed.

The guard checks that the mention's needle lands on the line the name sits on, which
`logcalls.handed` reports as the name's own line rather than the call's. On the one site registered
today those are one line. Two of the brain's five handed calls are wrapped by the formatter, the
abandonment warning and the no-reading line, each with the identifier on the line after the
opening parenthesis, and on either the template the guard's failure message suggests,
`<the call>({name},`, renders a needle the file does not carry, since a newline and an indent stand
between the parenthesis and the name.

Two shapes work and neither is written down. `{name},` alone lands on the name's line and is
bounded at the word edge, but it is a looser needle: it matches wherever the identifier is followed
by a comma, an `__all__` list among them, and only the guard's line check ties it to the call. A
template carrying the line break and the indent pins the call and is broken by any reformat that
moves the wrap, loudly, which is a needle failing on a change it has no opinion about.

What to weigh when it bites: a registry spelling that folds runs of whitespace in the needle, so one
template matches the call whether or not it is wrapped, against the rule in `needles.py` that a
needle is matched as written. That spelling is the same gap
[R-519](519-a-runbook-restates-a-declared-message-as-a-wrapped-prefix-nothing-ties.md) names from
the prose side.

## Trail

- 2026-09-02: opened by the close of
  [R-504](504-a-declared-message-and-a-different-word-in-the-call.md), whose mutation table
  measures a one-line call handed another word and says nothing about a wrapped one.
