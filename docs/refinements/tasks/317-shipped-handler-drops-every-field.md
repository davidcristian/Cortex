# The shipped handler drops every structured field

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

The brain configures logging once, at its process entry:
`logging.basicConfig(level=logging.INFO)` in `cortex_orchestrator.__main__`. That installs the
stdlib default format, `%(levelname)s:%(name)s:%(message)s`, which renders the message and nothing
else. Every `extra` field this repo attaches is therefore invisible in `docker compose logs brain`,
which is the only place an operator reads them.

The fields are not decoration. A rejected history fold carries `capped` and `chars`, and they are
the whole diagnosis: which of the fold's causes fired, and therefore whether the fix is a larger
`RECAP_MAX_TOKENS` or a rewritten instruction. A stranded handoff carries its `handoff` id, a
retried subagent its `task_id`, a forgone recall its `session_id` and `turn_id`. All of it is
written, none of it is printed.

Two adapters already work around this one at a time. `LoggingRecallSink` serializes its fields into
the message as well as onto the record, saying in its own docstring that a plain stdlib formatter
shows only the message and that the tool audit's adapter learned the same thing; the rank fallback
in `rerank_judge.py` spells `capped=` and `chars=` into its message for exactly that reason. Three
hand-rolled renderings are two more than the problem deserves, and every one of them is a second
spelling of a field that is already on the record.

The fix is one formatter at the entry point, not a fourth rendering: a `logging.Formatter` that
appends whatever a record carries beyond the standard `LogRecord` attributes, or a JSON line
formatter if the deployment would rather collect than read. Either way it belongs beside
`basicConfig`, since handler configuration lives at the process entry and nowhere else, and the
model manager's own entry (`cortex_model_manager.server`, which calls `basicConfig` with a
configured level) wants the same treatment. The three manual renderings can then stay as harmless
redundancy or come out, which is a judgement for whoever lands the formatter.

## Trail

- 2026-08-19: Opened by the close of [R-309](309-a-silent-judge-fallback.md), whose rank fallback
  had to spell its own two fields into its message to reach a reader at all.
