# An ok audit line carries a size where the correction is

**Status:** open, fix when it bites
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** a reading over the tool audit that asks how often a turn was corrected, or an
operator reading a failed turn's trail to see what a tool told the model before it gave up.

Opened 2026-09-06 by the close of
[582](582-the-not-found-answer-is-the-one-correction-the-audit-records-as-ok.md), which decided
that a call the server ran and answered empty is recorded `ok` even when its answer corrects the
model.

`LoggingAuditSink.record` writes `error` with the result detail when `invocation.ok` is false and
`result_chars` with the length alone when it is true
(`brain/packages/tools/src/cortex_tools/audit.py`). The reason is stated where it is written and
still holds: a successful file read can be large or sensitive, and the trail is not the place for
its content. The consequence is that an answer which corrected the model and is recorded `ok`
leaves nothing of that correction on the line. `read_email`'s not-found answer is one such answer
by decision, and `search_emails` answering no matches is another.

So the audit trail can be read for the calls a sidecar declined and cannot be read for the turns a
tool corrected. An operator working back from a turn that ended badly sees a character count on
the read that told the model to search again, and nothing on the line that says so.

**What would close it.** A decision on whether the trail should carry more than a size for an `ok`
answer, and if it should, the shape that does not put a file's contents in the logs: a bounded
first line, a flag the sidecar declares beside its answer, or a count of answers matched against
the own-text registry, which already holds every sentence the brain re-stamps as its own. If it
should not, a sentence in `docs/modules/brain-tools.md` saying that a corrected turn is not
readable from the trail and where it is readable instead.

## Trail

- 2026-09-06: opened by the close of
  [582](582-the-not-found-answer-is-the-one-correction-the-audit-records-as-ok.md), which
  recorded what a reading over `ok` counts and left what an `ok` line carries alone.
