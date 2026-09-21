# Nothing compares the runbook's trace question with the key the adapter sends

**Status:** done 2026-09-13
**Area:** repo-checks
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

The per-request trace budget's wire name is declared once, as `TRACE_BUDGET_KEY` in
`brain/packages/inference/src/cortex_inference/request.py`, and `trace_probe.py` imports it so the
probe that asks a server about the key and the request that sends it cannot disagree. Outside Python
it was retyped: the GPU runbook prints a `curl` whose body has the key, and its prose names it twice
more; `docs/modules/brain-inference.md` and `docs/modules/brain-orchestrator.md` state the contract
with the key in it; the subagents runbook names it in the paragraph about adding it on top of the
flags. No `crosscheck` entry compared any of those with the declaration.

What a mismatch costs is one operator reading. The runbook's `curl` is how a person asks their own
engine the question the brain asks at boot, and a key the adapter no longer sends leaves that
command answering about something the deployment does not do, with a `200` that reads as "this build
does not implement it". The Python halves were already safe: the adapter and the probe share the
constant, and `test_backend.py` asserts the rendered key as a literal.

**What closed it.** One `Constant` in the cross-tree registry, with the declaring `Site` on
`TRACE_BUDGET_KEY` and one mention per place outside Python. It went into a new registry part,
`scripts/tracecouplings.py`, the fourteenth that `crosscheck.CONSTANTS` is built from, because the
subject fits none of the thirteen already there. The engine owns this name rather than this repo, so
the entry's reason is the operator's command rather than a rename anybody here would make, and that
reason is written into the entry.

## History

- 2026-09-12: opened by the review of the trace-budget family, which read the GPU runbook's `curl`
  against `TRACE_BUDGET_KEY` and found nothing comparing them. That review's decisions are in
  [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md).
- 2026-09-13: done. Every claim held: the key is declared once, `trace_probe.py` imports it, no
  `scripts/` module named it, and each place the entry listed was still there. Four more were added
  to the six listed: the prose beside the code in `request.py`, `trace_probe.py` twice, `backend.py`
  and the orchestrator's `config.py` each type the name without importing it, so a rename would move
  the declaration and leave the sentence next to it naming the key that went. Two mutations proved
  it fails. What stayed out, the leak denominator in both runbooks and every table that names a cell
  by the key it used, is readings taken on a date.
