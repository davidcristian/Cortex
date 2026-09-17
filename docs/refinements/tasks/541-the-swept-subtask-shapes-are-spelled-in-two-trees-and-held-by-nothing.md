# The swept subtask shapes are spelled in two trees and held by nothing

**Status:** open, fix when it bites
**Area:** repo-gates
**Trigger:** the driver's default instruction moving, which `git log -S` over its text in
`brain/packages/orchestrator/tests/test_envelope_cost_live.py` shows as any commit after the
harness's own of 2026-08-26, or a reading at the origin record publishing `stood` alone with
`no judge is declared for this shape` for a shape its sweep asked. That phrase occurs once in the
origin record today, in the addendum describing the mechanism.
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)
**Verified:** 2026-09-17

Opened 2026-09-04 by the close of
[R-507](507-the-floor-sees-only-the-failures-a-machine-can-name.md), which put the three swept
instructions into `scripts/envelopejudges.py` as the shapes a judge is declared for.

The summarization instruction is spelled in eight places, counted on 2026-09-17 with `git grep -F`
over its text: the driver's own `CORTEX_ENVELOPE_INSTRUCTION` default in
`brain/packages/orchestrator/tests/test_envelope_cost_live.py`, the judge table in
`scripts/envelopejudges.py`, the docstring of `scripts/envelopesamples.py`, four test files under
`scripts/tests/` (the floor, judges, pairs and samples suites), and the origin record's prose; the
runbook does not spell it. The judge table now declares four shapes, a second summarization asking
to keep the report's figures having joined it on 2026-09-13. The other three are spelled in the
judge table, in one or two of those test files and in the origin record's prose, and nowhere in code
a sweep runs, since a sweep passes them through the environment variable. No gate holds any of the
four: no `scripts/*couplings.py` module spells one, so `scripts/crosscheck.py` has no entry over
them, and `scripts/settingscheck.py` holds compose files to the brain's settings classes and reads
no test harness.

**What is wrong with the present shape.** A driver that changed its default instruction would still
run and would still write a sample, and the reader would publish `stood` alone for a shape the
sweep really asked, saying `no judge is declared for this shape` about the one shape the arc is
built on. The report names the shape it could not judge, so nothing is silent, but the fault
arrives as a missing column in a live run rather than as a red gate on the edit that caused it.

**What would close it.** A `crosscheck` entry over the summarization instruction, holding the
driver's default to the shape declared in the judge table, in the manner
`scripts/subagentcouplings.py` holds the tier's budgets. The registry's vocabulary decides its
shape. A `Site` names an identifier a file declares, and the judge table passes each shape as a
positional argument to `Judge(...)`, so the shape has to be bound to a module-level name in
`scripts/envelopejudges.py` before it can be a site. The driver's default is an argument to
`os.environ.get` and cannot be a site either, so it is the `Mention`. A mention asks only that its
rendered template appear in the file, so a template of `"{value}."` finds the declared shape with
the final punctuation the table leaves off, and nothing has to compare prefixes. The three shapes
that exist only in the judge table have no second code site to be held to, and would stay held by
the report alone until a sweep recipe spells them somewhere a scan can read.

**Why it was left.** The reader reports the drift by name on the next run, and the whole arc is one
person's measurement rather than a shipped path.

## Trail

- 2026-09-04: opened by the close of
  [R-507](507-the-floor-sees-only-the-failures-a-machine-can-name.md), which declared the three
  swept shapes in a second tree without registering any of them.
- 2026-09-11: read against the tree and the trigger has not fired. `git log -S` over the driver's
  default finds one commit, the harness's own on 2026-08-26, so the shipped instruction has not
  moved; the judge table still writes its three shapes without final punctuation and `declared`
  still matches on a reduced prefix; no `scripts/*couplings.py` module spells any of the three, so
  the registry still holds nothing over them; and the sweep-columns reading on the origin record,
  288 runs on 2026-09-11, published `delivered` for every cell of all three shapes, so no report has
  yet carried `stood` alone for a shape a sweep asked. The count of places above was re-taken by
  grep and corrected: it read four, naming the runbook, which spells none of the shapes, and missed
  the samples module's docstring and three test files.
- 2026-09-17: read against the tree and not fired. `git log -S` over the driver's default still
  finds only the harness's own commit, and the origin record carries `no judge is declared for this
  shape` once, in the mechanism's own addendum; the 2026-09-13 reading of the fourth shape published
  its control arm at 32 of 32 on both picks, so it was judged. Three corrections. The judge table
  declares four shapes, not three. The summarization instruction has eight places, the pairs suite
  added on 2026-09-11 being a fourth test file that spells it. And the remedy's claim that a needle
  would have to compare prefixes was wrong: a mention is a search for its rendered template, which
  can carry the final punctuation itself, and what the entry really needs is a module-level name
  for the shape, since a site names a declared identifier and the table passes its shapes
  positionally. The twelfth cross-tree scan, `scripts/settingscheck.py`, reads compose files and
  settings classes and does not reach the harness.
