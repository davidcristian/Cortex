# The admission wait's shipped default is written in three places and registered in none

**Status:** done 2026-08-23
**Area:** repo-checks
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

`DEFAULT_ADMISSION_WAIT_S = 3600.0` is declared in
`brain/packages/core/src/cortex_core/scheduler.py` and repeated in two documents:
`docs/runbooks/subagents-cpu.md` as "`CORTEX_SUBAGENTS_ADMISSION_WAIT_S` (default 3600 s)" and
`docs/modules/brain-orchestrator.md` as "`admission_wait_s: float = 3600.0`". No row of the
constant registry names it, so retuning the declaration alone leaves both documents quoting a
bound no spawn is given.

The bound beside it is already registered this way. `SUBAGENT_COUPLINGS` in
`scripts/subagentcouplings.py` has the delegated run's shipped deadline with one declaration and
three matches, in the two forms the two kinds of reader write: a whole count of seconds where an
operator says it out loud, and the field's own declaration with its decimal point where a module
contract restates it. The admission wait's two are the same two forms, so the row is the run
deadline's own with the numbers changed. It is missing because the deadline's row was written when
the deadline was added, while the wait's declaration predates the registry.

## History

- 2026-08-23: opened by the close of
  [369](369-the-run-deadline-under-the-queue-is-prose-only.md), whose validator put the admission
  wait beside the run deadline in one comparison and sent a reader to a registry that covers one
  and not the other. Recorded in ADR-0047 decision 4.
- 2026-08-23: closed as one entry in `scripts/subagentcouplings.py`, one declaration and four
  matches. The entry's count was low, and one of its misses is code. It names two documents; the
  tree has five places. The two it missed besides the code are
  [modules/brain-core.md](../../modules/brain-core.md), which states the constant by name, and
  `brain/packages/core/src/cortex_core/subagents.py`, whose comment above the run deadline states
  the ordering "the pool's 600 s stall ceiling and its 3600 s admission wait". That is the third
  entry in a row framed as a prose gap whose misses include code. Its open question, whether the
  900 s and 1800 s batch waits belong in the row, is answered by the derived-literal ruling made
  hours earlier: those are consequences of this value and of a measured batch, so a search text
  over either would fail when the measurement moved, and they stay out. Two more kinds stay out:
  [index.md](../../index.md)'s catalogue sentence, which describes a decision record, and the two
  unit suites checking the default, which run on every commit. Five planted changes each exited 1
  and each restoration returned the check to passing, with four controls staying green, one of them
  `DEFAULT_SPILL_DWELL_S`, a different constant that also writes 3600 s in the same contract. One
  residue filed: the stall ceiling under this bound is stated in the same three places and
  registered in none ([R-402](402-the-stall-ceiling-is-ordered-against-two-held-bounds.md)).
