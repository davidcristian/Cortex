# The swept subtask shapes are spelled in two trees and held by nothing

**Status:** open, fix when it bites
**Area:** repo-gates
**Trigger:** a report publishing `stood` alone for a shape the sweep did ask, which is what a
changed instruction looks like from the reader's side.
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

Opened 2026-09-04 by the close of
[R-507](507-the-floor-sees-only-the-failures-a-machine-can-name.md), which put the three swept
instructions into `scripts/envelopejudges.py` as the shapes a judge is declared for.

The summarization instruction is now spelled in four places: the driver's own
`CORTEX_ENVELOPE_INSTRUCTION` default in
`brain/packages/orchestrator/tests/test_envelope_cost_live.py`, the judge table in
`scripts/envelopejudges.py`, this ADR's prose, and the runbook's. The other two shapes are spelled
in the judge table and in prose, and nowhere in code that runs, since a sweep passes them through
the environment variable. `scripts/crosscheck.py` holds no entry over any of them.

**What is wrong with the present shape.** A driver that changed its default instruction would still
run and would still write a sample, and the reader would publish `stood` alone for a shape the
sweep really asked, saying `no judge is declared for this shape` about the one shape the arc is
built on. The report names the shape it could not judge, so nothing is silent, but the fault
arrives as a missing column in a live run rather than as a red gate on the edit that caused it.

**What would close it.** A `crosscheck` entry over the summarization instruction, holding the
driver's default to the shape declared in the judge table, in the manner
`scripts/subagentcouplings.py` holds the tier's budgets. The two shapes that exist only in the
judge table have no second code site to be held to, and would stay held by the report alone until
a sweep recipe spells them somewhere a scan can read.

**Why it was left.** The reader reports the drift by name on the next run, the whole arc is one
person's measurement rather than a shipped path, and the registry entry costs a coupling in a
vocabulary whose match rule is an opening rather than an equality: the judge table deliberately
writes the shape without its final punctuation, so a needle over the two would have to compare
prefixes and not values.

## Trail

- 2026-09-04: opened by the close of
  [R-507](507-the-floor-sees-only-the-failures-a-machine-can-name.md), which declared the three
  swept shapes in a second tree without registering any of them.
