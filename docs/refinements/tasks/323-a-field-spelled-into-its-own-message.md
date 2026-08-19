# A field spelled into its own message now prints twice

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

The brain's process entries now install a formatter that renders whatever a record carries beyond
the standard `LogRecord` attributes, so a field attached with `extra=` reaches an operator's line
on its own. About twenty log sites still spell the same field into the message as well, because
that was the only way to be read before the formatter existed. Each of them now prints its field
twice: `started a model process: model=cortex pid=41 port=8081 model=cortex pid=41 port=8081`.

The family is `model=%s`, `pid=%d`, `error=%s` and their siblings, and it runs across
`cortex_model_manager` (`supervisor.py`, `server.py`, `adapter.py`, `api.py`, `children.py`,
`device_memory.py`), `cortex_core` (`residency_sweep.py`, `residency_moves.py`,
`residency_regain.py`, `residency_watch.py`) and `cortex_orchestrator` (`swap_builders.py`). The
three the formatter's own change removed, the two audit sinks and the rank fallback, were taken
first because each was a whole JSON object or a documented reading rather than two short tokens.

Two things make this larger than a sweep of format strings, and they are why it was filed rather
than folded in. Every one of these messages is what a runbook's `grep` is written against, so
`docs/runbooks/model-swap.md`, `llamacpp-gpu.md` and their neighbours have to move with the code;
and each site's tests assert on `getMessage()`, so the assertions move to the rendered line the way
the three already converted did. The cost of leaving it is legibility rather than correctness: a
doubled short token is ugly and reads as a bug in the formatter, which is the one thing a reader
should not have to rule out mid incident.

## Trail

- 2026-08-19: Opened by the close of
  [R-317](317-shipped-handler-drops-every-field.md), whose survey of hand-rolled renderings named
  three and whose re-derivation from the tree found this fourth family beside them.
