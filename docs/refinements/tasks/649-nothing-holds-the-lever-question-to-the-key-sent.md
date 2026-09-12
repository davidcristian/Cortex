# Nothing holds the runbook's lever question to the key the adapter sends

**Status:** landed 2026-09-13
**Area:** repo-gates
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-09-12 by the sweep that re-derived the trace-budget family
([R-496](496-the-trace-lever-is-answered-once-per-boot.md) and its three siblings), which read the
runbook's `curl` and the adapter's constant side by side and found nothing comparing them.

The per-request trace budget's wire name is declared once, as `TRACE_BUDGET_KEY` in
`brain/packages/inference/src/cortex_inference/request.py`, and `lever.py` imports it so the probe
that asks a server about the key and the request that carries it cannot disagree. Outside Python it
is retyped: the GPU runbook prints a `curl` whose body carries the key, and its prose names it twice
more; `docs/modules/brain-inference.md` and `docs/modules/brain-orchestrator.md` state the contract
with the key in it; the subagents runbook names it in the paragraph about adding it on top of the
flags. No `crosscheck` entry holds any of those to the declaration.

What drift costs is one operator reading. The runbook's `curl` is how a person asks their own engine
the question the brain asks at boot, and a key the adapter no longer sends leaves that command
answering about something the deployment does not do, with a `200` that reads as "this build does not
implement it". The Python halves are safe already: the adapter and the probe share the constant, and
`test_backend.py` asserts the rendered key by literal, which is the right way to pin a wire name.

**What would close it.** One `Constant` in the registry whose vocabulary the
[ADR-0029](../../adr/ADR-0029-vision-screen-capture.md) cross-language-constant addendum argues, with
the declaring `Site` on
`TRACE_BUDGET_KEY` and a mention per far side: the `curl` body's `"{value}":-2`, the runbook's prose
backticks, and the two module docs. The engine owns this name rather than this repo, so the entry's
reason is the operator's command rather than a rename anybody here would make, and that reason should
be written into the entry instead of the usual one. A mutation table over `scripts/` tests proves it
fails, the way every other coupling's does.

## Trail

- 2026-09-13: landed. The premise held on every claim: the key is declared once as
  `TRACE_BUDGET_KEY`, `lever.py` imports it, no `scripts/` module named it, and each far side the
  entry listed was still there. It went in as one `Constant` in a new registry part,
  `scripts/levercouplings.py`, the fourteenth `crosscheck.CONSTANTS` is joined from, because the
  subject belongs under none of the thirteen already there. Four far sides were added to the six
  this entry listed: the prose beside the code in `request.py`, `lever.py` twice, `backend.py` and
  the orchestrator's `config.py` each type the name without importing it, and a rename would move
  the declaration and leave the sentence next to it naming the key that went. Two mutations prove
  it fails, in the [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) addendum of this date, which
  also records what stayed out: the leak denominator in both runbooks and every ADR table that
  names a cell by the key it carried are readings taken on a date.
- 2026-09-12: opened by the sweep of the trace-budget family, which read the GPU runbook's lever
  `curl` against `TRACE_BUDGET_KEY` and found the two held by nothing. The sweep's readings are in
  the [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) addendum of that date.
