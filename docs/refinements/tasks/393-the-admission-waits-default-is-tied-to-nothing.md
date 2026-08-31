# The admission wait's shipped default is spelled in three places and tied in none

**Status:** landed 2026-08-23
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

`DEFAULT_ADMISSION_WAIT_S = 3600.0` is declared in `brain/packages/core/src/cortex_core/scheduler.py`
and spelled again in two documents: `docs/runbooks/subagents-cpu.md` writes it as
"`CORTEX_SUBAGENTS_ADMISSION_WAIT_S` (default 3600 s)" and `docs/modules/brain-orchestrator.md` as
"`admission_wait_s: float = 3600.0`". No row of the constant scan's registry names it, so retuning
the declaration alone leaves both documents quoting a bound no spawn is given.

The bound beside it is already held exactly this way. `SUBAGENT_COUPLINGS` in
`scripts/subagentcouplings.py` carries the delegated run's shipped deadline with one site and
three mentions, in the two spellings the two kinds of reader write it in: a whole count of seconds
where an operator says it out loud, and the field's own declaration with its point where a module
contract restates it. The admission wait's two mentions are the same two spellings, so the entry
that holds it is the run deadline's own with the numbers changed, and the reason it is missing is
that the deadline's row was written when the deadline landed while the wait's declaration predates
the registry.

Worth deciding while doing it: whether the wait's derivation sentences in the same runbook (the
900 s and 1800 s batch waits the bound is twice and four times) belong in the row as mentions of
their own. They are not spellings of this constant, they are the arithmetic under it, so the scan
cannot hold them to it, and the pair moving without the sentence is the failure
[207](207-whole-subtask-figure-off.md) already describes from the other side.

## Trail

- 2026-08-23: Opened by the close of
  [369](369-the-run-deadline-under-the-queue-is-prose-only.md), whose validator put the admission
  wait beside the run deadline in one comparison and sent a reader to the registry that already
  holds the one and not the other. Recorded in the ADR-0009 queue addendum.
- 2026-08-23: landed as one entry in `scripts/subagentcouplings.py`, one site and four mentions.
  **The entry's count was low, and one of its misses is code.** It names two documents; the tree
  carries five far sides. The two it missed besides the code are
  [modules/brain-core.md](../../modules/brain-core.md), which states the constant by name, and
  `brain/packages/core/src/cortex_core/subagents.py`, whose comment above the run deadline asserts
  the ordering "the pool's 600 s stall ceiling and its 3600 s admission wait". That is the third
  entry in a row framed as a prose gap whose misses include code. **Its own open question is
  answered by the derived-literal ruling**, which landed hours before this was picked up: the
  1800 s and 900 s the bound is twice and four times are consequences of this value and of a
  measured batch, so a needle over either would fail when the measurement moved, and they stay
  out. Two more kinds stay out: [index.md](../../index.md)'s catalogue sentence, whose subject is a
  dated addendum and which sorts with the decision records it indexes, and the two unit suites
  asserting the default, which run on every commit and hold themselves. Five planted drifts each
  exited 1 and each restoration returned the gate to green, with four controls staying green, one
  of them `DEFAULT_SPILL_DWELL_S`, a different constant spelling 3600 s in the same contract;
  tabled in the ADR-0029 admission-wait addendum. One residue filed: the stall ceiling under this
  bound is stated in the same three places and tied in none
  ([R-402](402-the-stall-ceiling-is-ordered-against-two-held-bounds.md)).
