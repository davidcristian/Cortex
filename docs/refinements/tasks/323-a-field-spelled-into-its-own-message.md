# A field spelled into its own message now prints twice

**Status:** landed 2026-08-19
**Area:** cross-cutting
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

The brain's process entries now install a formatter that renders whatever a record carries beyond
the standard `LogRecord` attributes, so a field attached with `extra=` reaches an operator's line
on its own. About twenty log sites still spell the same field into the message as well, because
that was the only way to be read before the formatter existed. Each of them now prints its field
twice: `started a model process: model=cortex pid=41 port=8081 model=cortex pid=41 port=8081`.

The group is `model=%s`, `pid=%d`, `error=%s` and their siblings, and it runs across
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

- 2026-08-19: Opened by the close of [R-317](317-shipped-handler-drops-every-field.md), whose survey
  of hand-rolled renderings named three and whose re-derivation from the tree found this fourth
  group beside them.
- 2026-08-19: Landed as the ADR-0038 twice-printed-field addendum. Re-derived from the tree first,
  which found **31** sites and not "about twenty", across 13 files: the eleven this entry named,
  plus `swap_conductor.py` and `swap_recovery.py`. Every one of them now logs a constant sentence
  and carries its values as fields alone, so a value appears once on the line and a runbook's `grep`
  matches every instance of a line rather than the one whose id it quoted. No field was lost: every
  value taken out of a message was already attached, which is why nothing had to be rescued, and
  each site's assertions moved onto `PlainFormatter().format(record)` rather than staying on a
  message that no longer carries them. Seven messages needed rewording rather than a deleted token,
  the two device-memory lines whose value was a word of the sentence and the five `%r` clauses that
  now name their subject generically. Two shapes deliberately keep a value in prose: a message that
  is also a raised exception's text, and the sweep's own predicate (`could not be started`), which
  is not a field and so cannot double. The runbooks moved in the same commit: `model-swap.md` (three
  quoted lines and the log-reading pointer), `local-dev-wsl.md` (a fourth reading rule) and
  `brain-model-manager.md`. Verified live against the real sidecar, before and after, in `docker
  compose logs model-host`. What it opened is [R-325](325-a-raised-message-is-also-a-logged-one.md),
  the six messages that are logged and raised, and
  [R-326](326-a-line-that-names-nothing-it-happened-to.md), the lines at the other end of the
  question that attach no field at all.
