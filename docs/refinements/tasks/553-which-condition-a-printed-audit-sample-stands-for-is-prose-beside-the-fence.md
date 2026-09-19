# Which condition a printed audit sample stands for is only stated in prose

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)
**Verified:** 2026-09-19
**Trigger:** a printed sample of the tool audit's line in `docs/runbooks/tools-mcp.md` whose
introducing sentence names a condition other than the one its fields describe, or a whole-line
assertion of that line added anywhere under `brain/packages/tools/tests` with a field set the
runbook does not print. Both are countable: read each sample's field names against the clause
introducing it, and compare the set of field lists `scripts/assertedlines.proven` returns for this
sink with the set the runbook prints.

`scripts/samplecheck.py` checks that each sample is some line the suite asserts. It does not check
which one. The sentence before the samples says the second line is a failure and the fifth a
schedule fire, and nothing compares that sentence with the fields on the line it introduces, so a
runbook whose failure line and fire line swapped places would pass. Nothing checks that the runbook
prints every condition the suite asserts either, or that the suite asserts every branch the sink
has; today they match, and a whole-line assertion added for a new condition would leave the runbook
one short with every check green. That is the coverage question ADR-0045 filed as
[R-444](444-nothing-says-which-log-lines-a-runbook-should-print.md) for log lines generally.

The two sides do not match one for one, which constrains any coverage rule.
`scripts/assertedlines.proven` returns six lines for this sink and the runbook prints five samples,
because the suite asserts the plain success twice, once for a call with an argument and once for a
dispatch whose caller created no id, and both lines have the same field set. So the comparison has
to be between the two sets of field lists, not a count of assertions against samples.

The which-condition half needs a grammar for the clause introducing a sample, which is the prose
reading the sample check declined to do at its founding. The coverage half is a set comparison over
two readings the tree already makes, and the rule it would add is that a sink checked against its
suite has every asserted condition printed; whether that rule is right is the open question, since a
suite may assert a line for a reason that is not an operator's. `samplecheck.py` stands at 289 lines
against the 300-line cap, so the rule costs a split of that file as well. `_proven` also reads the
whole package suite rather than one module, so the set it returns includes lines other modules
print: the orchestrator's suite asserts a whole `cortex.tools.audit` line written straight through
the logger to prove the shipped level, which no module in that package writes, and a rule over every
asserted condition would demand that one be printed. Widening the reader, as
[R-554](554-a-whole-line-asserted-through-an-f-string-or-a-helper-is-not-read-as-proven.md)
proposes, would grow the set a coverage rule compares against.

## History

- 2026-09-05: opened by the close of
  [R-523](523-the-tool-audit-line-is-described-in-prose-because-its-fields-vary-by-condition.md),
  whose mutation table covers membership and order per sample and says nothing about which sample is
  which.
- 2026-09-09: checked, and one count repaired. Neither trigger clause has fired. The runbook prints
  five samples of `cortex.tools.audit`, and their field names match the introducing sentence:
  success first, the failure with `error` second, the cortex call with `call_id` and `turn_id`
  third, the delegated call with `task_id` fourth and the schedule fire with `item_id` fifth. The
  body had said the two sides matched one for one; `assertedlines.proven` returns six lines over
  those five distinct field sets.
- 2026-09-12: checked again, with the cost claim repaired. Neither clause has fired and the five
  samples are unchanged. The entry priced the coverage half at a few lines in `samplecheck.py`, and
  that file is at 287 of the 300-line cap, so the rule no longer fits beside the reading it needs
  and a split comes with it.
- 2026-09-14: checked again with nothing repaired. Neither clause has fired, the same five samples
  are printed in the stated order, `assertedlines.proven` returns the same six lines, and
  `samplecheck.py` still stands at 287 lines.
- 2026-09-15: checked again, with one number and one cost claim repaired. Neither clause has fired
  and the samples are unchanged. `samplecheck.py` now stands at 289 lines rather than 287. New
  constraint, found by reading `_proven` against a second module: the suite it reads is the
  package's rather than the module's, and the orchestrator's has a `cortex.tools.audit` line no
  module in that package prints, so a coverage rule over every asserted condition would demand a
  runbook print it.
- 2026-09-19: checked again, with the trigger's second clause widened to the suite the reader really
  reads. Neither clause has fired and the same five samples and six asserted lines stand, all six
  from `test_audit.py`. The clause named that one file, while `_proven` reads every file under
  `brain/packages/tools/tests`, and on 2026-09-17 that directory gained `audit_contract.py`,
  `test_audit_contract.py` and `test_audit_file.py`. None of the three asserts a whole rendered
  line, but one added to any of them would grow the set, so the clause now names the directory.
  Neither of that day's audit changes adds a condition: the file sink keeps what the line prints,
  and withholding a nested secret key changes a value, not a field. `samplecheck.py` still stands at
  289 lines.
