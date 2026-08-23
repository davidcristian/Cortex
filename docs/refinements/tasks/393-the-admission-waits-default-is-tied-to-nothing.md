# The admission wait's shipped default is spelled in three places and tied in none

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

`DEFAULT_ADMISSION_WAIT_S = 3600.0` is declared in `brain/packages/core/src/cortex_core/scheduler.py`
and spelled again in two documents: `docs/runbooks/subagents-cpu.md` writes it as
"`CORTEX_SUBAGENTS_ADMISSION_WAIT_S` (default 3600 s)" and `docs/modules/brain-orchestrator.md` as
"`admission_wait_s: float = 3600.0`". No row of the constant scan's registry names it, so retuning
the declaration alone leaves both documents quoting a bound no spawn is given.

Its neighbour is already held exactly this way. `SUBAGENT_COUPLINGS` in
`scripts/subagentcouplings.py` carries the delegated run's shipped deadline with one site and
three mentions, in the two spellings the two kinds of reader write it in: a whole count of seconds
where an operator says it out loud, and the field's own declaration with its point where a module
contract restates it. The admission wait's two mentions are the same two spellings, so the entry
that holds it is the neighbouring one with the numbers changed, and the reason it is missing is
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
