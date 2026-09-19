# The tool audit line is described in prose because its fields vary by condition

**Status:** done 2026-09-05
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

`brain/packages/tools/src/cortex_tools/audit.py` binds `fields`, grows it by `update` with whichever
of the five work identities the dispatch had, gives it `result_chars` or `error` by whether the call
succeeded, and hands it to `_logger.info`. No one sample can print what that attaches, because the
set varies by condition, so `logfields.py` refuses it at the first use after its binding. What the
tools runbook says about the line, `docs/runbooks/tools-mcp.md` describing the tool's name, `ok`,
the arguments, `trust`, either `result_chars` or `error` and the work identities, is therefore
compared with nothing, which is the shape the swap runbook's warning bullet went stale in before it
was printed.

Two ways to close it. A sample grammar for a field present by condition, one sample per condition
with the reader following the `if` that sets the field, which is the branch-following declined
elsewhere. Or name the sink's own suite in the registry beside the runbook's field list, the way
ADR-0045 decision 15 names it beside the message, so the prose and the assertion are connected by a
search text. The second costs one registry entry per field and covers the names, not the conditions.

## History

- 2026-09-02: opened by the close of
  [R-516](516-a-field-list-composed-above-its-call-cannot-be-quoted.md), which measured the audit
  line refused as bound at line 65 and used again at line 72, and left its prose where it was.
- 2026-09-04: the first half of the trigger fired and the entry became actionable. Reading the
  runbook's list against the sink found one field missing, `at`, which the sink attaches on every
  call: the prose named the tool, `ok`, the arguments, `trust`, either `result_chars` or `error`,
  the four work ids and `call_id`, eleven of the twelve names a line can have. The sentence is
  corrected to name the timestamp. The second half has not fired: reading the `extra=` of every
  brain log call and following the seven that name a binding finds six read cleanly and one refused,
  the audit sink's at line 89, so this is still the only line in the brain whose field set varies by
  condition.
- 2026-09-05: closed, by neither proposed option (ADR-0045 decision 11). Every count held: 94
  `extra=` expressions, seven naming a binding, six read and one refused at `audit.py:89`, twelve
  possible names. What the entry had wrong is its second option: a registry entry needs a declaring
  site, seven of the twelve names are literal keys declared nowhere, the runbook's sentence named
  ten of them and described two in prose, `session_id` had no tools-runbook mention at all, and a
  search text covers a name and never a set, so a field the sink gained would have missed nothing.
  What was built instead is a chain: the runbook prints five rendered samples of the line, one per
  shape, and `scripts/samplecheck.py` compares each with a whole line the sink's own suite asserts
  against the shipped formatter (`scripts/assertedlines.py`), which pytest compares with the sink.
  Measured over the check suite (1,709 tests), `check-samplecheck` (12 samples, 5 compared with the
  suite) and the sink's suite (13 tests): a field dropped from a sample, a sample reordered, a field
  the sink gained or renamed with the suite updated, and a suite assertion loosened to a containment
  each fail. Opened
  [R-553](553-which-condition-a-printed-audit-sample-stands-for-is-prose-beside-the-fence.md) and
  [R-554](554-a-whole-line-asserted-through-an-f-string-or-a-helper-is-not-read-as-proven.md).
