# The shipped handler drops every structured field

**Status:** landed 2026-08-19
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
- 2026-08-19: Landed as one formatter at both entry points, with the three renderings taken out.
  `cortex_core/log_fields.py` holds the pure half (which attributes are the record's own, how a
  value is written, what is withheld) and `cortex_core/log_format.py` the stdlib adapter:
  `PlainFormatter` appends `key=value` pairs in name order after the message, `PackedFormatter`
  writes one JSON object per line, and `configure_logging` installs whichever the env named.
  `plain` ships, because the operator this deployment has reads `docker compose logs brain` in a
  terminal whose stream also carries uvicorn's lines and llama.cpp's stderr, so a JSON default
  would buy no parseable stream and cost the only reader there is. `packed` is selectable by
  `CORTEX_LOG_FORMAT` (`CORTEX_MODELHOST_LOG_FORMAT` for the sidecar), both forwarded by compose
  and the default tied to its declaration by the cross-tree constant scan. The three manual
  renderings came out, since under `plain` each would have printed its fields twice, and the
  runbooks that read them survived: fields render in name order, so `capped=True chars=0` still
  appears adjacently and `grep "unjudged ranking"` still matches. The secret question the entry did
  not ask is answered in the formatter rather than left to callers: a field named for a secret
  prints `<redacted>`, and a URL's credential is stripped from the whole rendered line, message and
  traceback included. Verified live through `docker compose logs brain` in both renderings. The
  wider family of fields spelled into their own messages, which the entry's survey missed, is
  [R-323](323-a-field-spelled-into-its-own-message.md), and the unbounded length of a rendered
  value is [R-324](324-a-rendered-field-has-no-bound.md).
