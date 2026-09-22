# The shipped handler drops every structured field

**Status:** done 2026-08-19
**Area:** cross-cutting
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)

The brain configured logging once, at its process entry: `logging.basicConfig(level=logging.INFO)`
in `cortex_orchestrator.__main__`. That installs the stdlib default format,
`%(levelname)s:%(name)s:%(message)s`, which renders the message and nothing else. Every `extra`
field this repo attaches was therefore invisible in `docker compose logs brain`, which is the only
place an operator reads them.

The fields are the diagnosis. A rejected history fold has `capped` and `chars`, which say which
cause applied and therefore whether the fix is a larger `RECAP_MAX_TOKENS` or a rewritten
instruction. A stranded handoff has its `handoff` id, a retried subagent its `task_id`, a dropped
recall its `session_id` and `turn_id`.

Two adapters already worked around this one at a time. `LoggingRecallSink` wrote its fields into
the message as well as onto the record, and the rank fallback in `rerank_judge.py` wrote `capped=`
and `chars=` into its message for the same reason. Three hand-written renderings are two more than
the problem needs.

The fix is one formatter at the entry point: a `logging.Formatter` that appends whatever a record
has beyond the standard `LogRecord` attributes, or a JSON line formatter for a deployment that
collects rather than reads. It belongs beside `basicConfig`, and the model manager's own entry
(`cortex_model_manager.server`) needs the same.

## History

- 2026-08-19: Opened by the close of [R-309](309-a-silent-judge-fallback.md), whose rank fallback
  had to write its own two fields into its message to reach a reader at all.
- 2026-08-19: Fixed as one formatter at both entry points, with the three renderings removed.
  `cortex_core/log_fields.py` holds the pure half (which attributes are the record's own, how a
  value is written, what is withheld) and `cortex_core/log_format.py` the stdlib adapter:
  `PlainFormatter` appends `key=value` pairs in name order after the message, `PackedFormatter`
  writes one JSON object per line, and `configure_logging` installs whichever the environment
  names. `plain` ships, because the operator reads `docker compose logs brain` in a terminal whose
  stream also has uvicorn's lines and llama.cpp's stderr, so a JSON default would give no parseable
  stream and cost the only reader there is. `packed` is selected by `CORTEX_LOG_FORMAT`
  (`CORTEX_MODELHOST_LOG_FORMAT` for the sidecar), both forwarded by compose and the default
  checked against its declaration by the cross-tree constant scan. The three manual renderings came
  out, since under `plain` each would have printed its fields twice, and the runbooks that read
  them still work: fields render in name order, so `capped=True chars=0` still appears together and
  `grep "unjudged ranking"` still matches. The secret question the entry did not ask is answered in
  the formatter rather than left to callers: a field named for a secret prints `<redacted>`, and a
  URL's credential is stripped from the whole rendered line, message and traceback included.
  Verified live through `docker compose logs brain` in both renderings. The wider family of fields
  written into their own messages is [R-323](323-a-field-written-into-its-own-message-now-prints-twice.md), and the
  unbounded length of a rendered value is [R-324](324-a-rendered-field-has-no-bound.md).
