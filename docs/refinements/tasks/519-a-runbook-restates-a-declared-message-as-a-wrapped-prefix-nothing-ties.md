# A runbook restates a declared message as a wrapped prefix nothing checks

**Status:** done 2026-09-02
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

`cortex_core/brain_phase.py` binds `SPILLED_LOG_MSG`, a two-clause sentence, and hands it to
`_logger.warning`. `docs/runbooks/model-swap.md` describes that line in the spill watch's list and
quotes its first clause in italics, wrapped over two lines at the runbook's column. The call is
compared with the binding by `test_brain_phase.py`, which imports the constant and asserts
`getMessage()` against it. The quote is compared with nothing: a rewording of the constant leaves the
runbook describing a line the brain no longer writes, with every check passing.

The registry cannot cover it as written, for two reasons that are one gap. An entry renders
`{value}` as the whole declared value, and the runbook quotes a prefix; and a search text is matched
as written, so the wrap inside the quote is a newline and two spaces where the value has one space.
A rendered sample would cover the message, but the call's fields are composed above it, which is
[R-516](516-a-field-list-composed-above-its-call-cannot-be-quoted.md).

## History

- 2026-09-02: opened by the close of
  [R-504](504-a-declared-message-and-a-different-word-in-the-call.md), which measured the spill
  warning as covered by its own suite and found the restatement while checking which of the five
  handed messages any document quotes.
- 2026-09-02: closed by removal rather than by any of the three options weighed (ADR-0045 decision
  9). The close of [R-516](516-a-field-list-composed-above-its-call-cannot-be-quoted.md) made the
  warning's fields readable, so the swap runbook prints the warning as a fenced sample and the
  italic prefix is gone; the message is now compared whole by `check-samplecheck`, which a mutation
  measured as the constant reworded leaving `test_brain_phase.py` passing and the check failing. The
  registry form that folds whitespace was not built, and
  [R-518](518-a-registered-binding-handed-at-a-wrapped-call-has-no-one-line-needle.md) still names
  it from the call side.
