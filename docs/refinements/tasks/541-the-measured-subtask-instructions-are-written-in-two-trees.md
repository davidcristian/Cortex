# The measured subtask instructions are written in two trees and no check compares them

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Trigger:** the driver's default instruction changing, which `git log -S` over its text in
`brain/packages/orchestrator/tests/test_envelope_cost_live.py` shows as any commit after the
harness's own of 2026-08-26; or a reading at the origin record publishing `stood` alone with
`no judge is declared for this shape` for an instruction its measurement asked. That phrase occurs
once in the origin record today, in the decision describing the mechanism.
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)
**Verified:** 2026-09-17

The summarization instruction is written in eight places, counted on 2026-09-17 with `git grep -F`
over its text: the driver's own `CORTEX_ENVELOPE_INSTRUCTION` default in
`brain/packages/orchestrator/tests/test_envelope_cost_live.py`, the judge table in
`scripts/envelopejudges.py`, the docstring of `scripts/envelopesamples.py`, four test files under
`scripts/tests/` (the floor, judges, pairs and samples suites), and the origin record's prose. The
runbook does not contain it. The judge table declares four instructions, a second summarization
asking to keep the report's figures having joined it on 2026-09-13. The other three are written in
the judge table, in one or two of those test files and in the origin record, and nowhere in code a
measurement runs, since a measurement passes them through the environment variable. No check
compares any of the four: no `scripts/*couplings.py` module contains one, so `scripts/crosscheck.py`
has no entry over them, and `scripts/settingscheck.py` compares compose files with the brain's
settings classes and reads no test harness.

A driver that changed its default instruction would still run and still write a sample, and the
reader would publish `stood` alone for the instruction the measurement really asked, saying
`no judge is declared for this shape` about the one instruction the measurement is built on. The
report names what it could not judge, so nothing is silent, but the failure arrives as a missing
column in a live run rather than on the edit that caused it.

**What would close it.** A `crosscheck` entry over the summarization instruction, comparing the
driver's default with the instruction declared in the judge table, the way
`scripts/subagentcouplings.py` compares the tier's budgets. A `Site` names an identifier a file
declares, and the judge table passes each instruction as a positional argument to `Judge(...)`, so
the instruction has to be bound to a module-level name in `scripts/envelopejudges.py` first. The
driver's default is an argument to `os.environ.get` and cannot be a declaration either, so it is the
`Mention`; a template of `"{value}."` finds the declared text with the final punctuation the table
leaves off. The three instructions that exist only in the judge table have no second place in code
to be compared against, and stay checked by the report alone until a recipe writes them somewhere a
scan can read.

**Why it was left.** The reader names the mismatch on the next run, and the whole measurement is one
person's work rather than a shipped path.

## History

- 2026-09-04: opened by the close of
  [R-507](507-the-floor-sees-only-the-failures-a-machine-can-name.md), which declared the three
  measured instructions in a second tree without registering any of them.
- 2026-09-11: read against the tree and the trigger has not fired. `git log -S` over the driver's
  default finds one commit, the harness's own on 2026-08-26; the judge table still writes its
  instructions without final punctuation and `declared` still matches on a reduced prefix; no
  `scripts/*couplings.py` module contains any of them; and the 288-run reading of 2026-09-11
  published `delivered` for every cell of all three, so no report has published `stood` alone. The
  count of places was retaken by grep and corrected: it read four, named the runbook, which contains
  none of them, and missed the samples module's docstring and three test files.
- 2026-09-17: read against the tree and not fired. `git log -S` still finds only the harness's own
  commit, and the origin record has `no judge is declared for this shape` once, in the mechanism's
  own decision; the 2026-09-13 reading of the fourth instruction published its control condition at
  32 of 32 on both picks, so it was judged. Three corrections: the judge table declares four
  instructions and not three; the summarization instruction has eight places, the pairs suite added
  on 2026-09-11 being a fourth test file; and the claim that a search text would have to compare
  prefixes was wrong, since a mention searches for its written template, which can include the final
  punctuation. What the entry really needs is a module-level name for the instruction.
  `scripts/settingscheck.py` reads compose files and settings classes and does not reach the
  harness.
