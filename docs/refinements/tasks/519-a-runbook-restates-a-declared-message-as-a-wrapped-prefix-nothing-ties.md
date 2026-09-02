# A runbook restates a declared message as a wrapped prefix nothing ties

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-09-02 by the close of
[R-504](504-a-declared-message-and-a-different-word-in-the-call.md), whose re-derivation found a
second declared message that a document restates, beside the tool audit's.

`cortex_core/brain_phase.py` binds `SPILLED_LOG_MSG`, a two-clause sentence, and hands it to
`_logger.warning`. `docs/runbooks/model-swap.md` describes that line in the spill watch's list and
quotes its first clause in italics, wrapped over two lines at the runbook's column. The call is
held to the binding by `test_brain_phase.py`, which imports the constant and asserts `getMessage()`
against it. The quote is held to the binding by nothing: a rewording of the constant leaves the
runbook describing a line the brain no longer writes, with every gate green, which is the shape the
constant registry exists for.

The registry cannot tie it as written, for two reasons that are one gap. A mention renders
`{value}` as the whole declared value, and the runbook quotes a prefix; and a needle is matched as
written, so the wrap inside the quote is a newline and two spaces where the value has one space. A
rendered sample would hold the message, but the call's fields are composed above it, which is
[R-516](516-a-field-list-composed-above-its-call-cannot-be-quoted.md).

Three ways to close it, in rising cost. Quote the whole sentence on one line in the runbook, which
is a line of prose near 200 characters in a file wrapped at 100, with a template rendering the
whole value. Split the constant into two bindings, the clause the runbook quotes and the rest,
joined at the call, which bends the module to the gate's reader, the objection the quotable-line
addendum recorded against rewriting a call to become quotable. Or give the registry a spelling that
folds whitespace and a way to render a declared prefix, which is the reader change
[R-518](518-a-registered-binding-handed-at-a-wrapped-call-has-no-one-line-needle.md) asks for from
the call side.

## Trail

- 2026-09-02: opened by the close of
  [R-504](504-a-declared-message-and-a-different-word-in-the-call.md), which measured the spill
  warning as held to its call by its suite and found the restatement while checking which of the
  five handed messages any document quotes.
