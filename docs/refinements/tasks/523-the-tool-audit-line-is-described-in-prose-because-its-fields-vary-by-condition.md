# The tool audit line is described in prose because its fields vary by condition

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** the tools runbook's description of the audit line found to disagree with the sink, or
a second brain line whose field set varies by condition arriving with a runbook that describes it.

Opened 2026-09-02 by the close of
[R-516](516-a-field-list-composed-above-its-call-cannot-be-quoted.md), which read the deep phase's
composed field lists and decided that the tool audit's stays unread.

`brain/packages/tools/src/cortex_tools/audit.py` binds `fields`, grows it by `update` with
whichever of the five work identities the dispatch carried, gives it `result_chars` or `error` by
whether the call succeeded, and hands it to `_logger.info`. No one sample can print what that
attaches, because what it attaches is a set that varies by condition, so `logfields.py` refuses it
at the first use after its binding rather than reading the five-key literal as the line. What the
tools runbook says about the line, `docs/runbooks/tools-mcp.md` describing the tool's name, `ok`,
the arguments, `trust`, either `result_chars` or `error` and the work identities, is therefore held
by nothing, which is the shape the swap runbook's warning bullet drifted into before it was
printed: six names in an order the formatter does not print and three missing.

Two ways to close it. A sample grammar for a field present by condition, say one sample per
condition with the reader following the `if` that sets the field, which is the branch-following
the entry above declined and would need the reader to say which branch a sample stands for. Or the
sink's own suite, `brain/packages/tools/tests/test_audit.py`, which asserts four whole rendered
lines already and could be named by the registry beside the runbook's field list the way the
declared-name addendum names it beside the message, so the prose and the assertion are tied by a
needle. The second costs one registry entry per field and holds the names, not the conditions.

## Trail

- 2026-09-02: opened by the close of
  [R-516](516-a-field-list-composed-above-its-call-cannot-be-quoted.md), which measured the audit
  line refused as bound at line 65 and used again at line 72, and left its prose where it was.
