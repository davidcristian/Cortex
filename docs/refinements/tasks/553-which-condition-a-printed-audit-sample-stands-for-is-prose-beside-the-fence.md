# Which condition a printed audit sample stands for is prose beside the fence

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
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
every branch the sink has; today the five match by construction, and a sixth whole-line assertion
added to the suite for a new shape would leave the runbook one short with every gate green, which
is the coverage question the sample-membership addendum filed as
[R-444](444-nothing-says-which-log-lines-a-runbook-should-print.md) for lines generally.

What a close would cost. The which-shape half wants a grammar for the clause introducing a sample,
which is the prose-reading the sample gate declined at its founding. The coverage half is a set
comparison over two readings the tree already makes, the fence's field lists against the suite's,
and is a few lines in `samplecheck.py` if the rule is that a sink held to its suite has every
asserted shape printed; whether that rule is right is the question, since a suite may assert a
line for a reason that is not an operator's.

## Trail

- 2026-09-05: opened by the close of
  [R-523](523-the-tool-audit-line-is-described-in-prose-because-its-fields-vary-by-condition.md),
  whose mutation table holds membership and order per sample and says nothing about which sample
  is which.
