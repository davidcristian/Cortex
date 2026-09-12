# Which condition a printed audit sample stands for is prose beside the fence

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-12
**Trigger:** a rendered sample of the tool audit's line in `docs/runbooks/tools-mcp.md` whose
introducing sentence names a shape other than the one its fields spell, or a whole-line assertion
added to `brain/packages/tools/tests/test_audit.py` with a field set the runbook's fence does not
print. Both are countable: read each sample's field names against the clause introducing it, and
compare the set of field lists `scripts/assertedlines.proven` returns for the sink against the set
the fence prints.

Opened 2026-09-05 by the close of
[R-523](523-the-tool-audit-line-is-described-in-prose-because-its-fields-vary-by-condition.md),
which replaced the runbook's prose enumeration of the line's fields with five fenced samples, each
held by `scripts/samplecheck.py` to a whole line the sink's own suite asserts.

The gate holds that each sample is some line the suite proves. It does not hold which one. The
sentence before the fence says the second line is a failure and the fifth a schedule fire, and
nothing compares that sentence to the fields on the line it introduces: a fence whose failure line
and fire line swapped places would pass, with the prose pointing a reader at the wrong shape. Nor
does anything hold the fence to printing every shape the suite asserts, or the suite to asserting
every branch the sink has; today the shapes match, and a whole-line assertion added to the suite
for a new shape would leave the runbook one short with every gate green, which is the coverage
question the sample-membership addendum filed as
[R-444](444-nothing-says-which-log-lines-a-runbook-should-print.md) for lines generally.

The two sides do not match one for one, which constrains the coverage rule.
`scripts/assertedlines.proven` returns six lines for the sink and the fence prints five samples,
because the suite asserts the plain success shape twice, once for a call carrying an argument and
once for a dispatch whose caller minted no id, and both lines carry the same field set. So the
comparison has to be
between the two sets of field lists, as the trigger above states it, and a rule counting assertions
against samples would report a shortfall on a tree where nothing is missing.

What a close would cost. The which-shape half wants a grammar for the clause introducing a sample,
which is the prose-reading the sample gate declined at its founding. The coverage half is a set
comparison over two readings the tree already makes, the fence's field lists against the suite's,
and the rule it would land is that a sink held to its suite has every asserted shape printed;
whether that rule is right is the question, since a suite may assert a line for a reason that is
not an operator's. It is no longer a few lines where it would go: `samplecheck.py` stands at 287
lines against the 300-line cap, and the rule needs a constant, a function and an accumulation in
`check` beside the docstring sentence that argues it, so the half costs a split of that file as
well. A second question arrives with
[R-554](554-a-whole-line-asserted-through-an-f-string-or-a-helper-is-not-read-as-proven.md): the
set the suite asserts is the set `assertedlines.py` can read, so widening that reader would grow
the set a coverage rule compares against, and a runbook printing every shape today would begin
failing on shapes the reader had not been able to see.

## Trail

- 2026-09-05: opened by the close of
  [R-523](523-the-tool-audit-line-is-described-in-prose-because-its-fields-vary-by-condition.md),
  whose mutation table holds membership and order per sample and says nothing about which sample
  is which.
- 2026-09-09: verified against the code, with one count in the body repaired. Neither clause of the
  trigger has fired. `docs/runbooks/tools-mcp.md` prints five samples of `cortex.tools.audit`, and
  reading each one's field names against the clause introducing it puts the success first, the
  failure carrying `error` second, the cortex call carrying `call_id` and `turn_id` third, the
  delegated call carrying `task_id` fourth and the schedule fire carrying `item_id` fifth, which is
  the order the sentence above the fence states. The body said the five sides matched one for one;
  `assertedlines.proven` returns six lines for the sink, over the five distinct field sets the
  fence prints, and that duplicate is now described above along with what it costs a coverage
  rule.
- 2026-09-12: verified again, with the cost claim repaired. Neither trigger clause has fired.
  `docs/runbooks/tools-mcp.md` still prints five samples of `cortex.tools.audit` in the order its
  introducing sentence states, success, failure, cortex call, delegated call, schedule fire, and
  `assertedlines.proven` still returns six lines for the sink over those same five distinct field
  sets, the plain success asserted twice. What moved is what the coverage half costs. The entry
  priced it at a few lines in `samplecheck.py`, and that file is at 287 of the 300-line cap, so the
  rule no longer fits beside the reading it needs and a split comes with it. The which-shape half is
  unchanged and still wants a grammar for a sentence.
