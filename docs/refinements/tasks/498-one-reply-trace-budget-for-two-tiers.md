# One reply trace budget reaches the deep phase as well as the cortex turn

**Status:** done 2026-09-14
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

`ReplyBoundsConfig.bounds()` builds one `GenerationBounds`, the composition root hands it to
`StreamEngines`, and `BrainPhase` passes the same value into the deep model's completion. That
sharing is deliberate for the two settings that were already there: a handoff is one turn continued,
so a deployment that capped a reply did not ask for the cap to lapse when the question got hard
enough to escalate (ADR-0048). The new count inherits it.

The server flags for the same setting are deliberately two, `CORTEX_REASONING_BUDGET` and
`CORTEX_REASONING_BUDGET_BRAIN`, because the two tiers are read on opposite terms: the cortex
answers while somebody watches, and the deep model was chosen for reaching an answer inside its
trace at all (ADR-0004). A deployment that shortens the cortex's thinking has no reason to have
shortened the deep model's, and with one request-level count it does both. The request wins where
both are named, since the tier flag is only the fallback.

## History

- 2026-08-29: opened by the close of
  [R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md), which added a per-request
  trace count to the bounds a turn and its deep continuation already share.
- 2026-09-07: the trigger has not fired. Both settings it names would have to be on together and
  neither is on at all. `CORTEX_REPLY_TRACE_TOKENS` is set by no compose file, recipe or workflow,
  and there is no `.env` at the repo root. `CORTEX_ESCALATION` is off by default in `config_swap.py`,
  and the GPU override names it only in a comment; the one place in the tree that sets it is a host
  task's compose snippet.
- 2026-09-12: the trigger has not fired and the premise holds line for line.
  `ReplyBoundsConfig.bounds()` builds one `GenerationBounds`; `wiring.py` hands it to
  `StreamEngines` as `bounds`; `engine.py` puts it on the cortex turn's `ToolLoopContext` and
  `brain_phase.py` puts the same `self._caps.bounds` on the deep continuation's. One reading is
  worth adding: the two tier flags express the split, but their default does not, and `crosscheck`
  compares those two defaults as one set on the argument that both tiers ship unbounded. So the
  first deployment to set the request count on an escalating stack bounds two traces that nothing
  else bounds.
- 2026-09-14: closed as the cheap half, the sentence rather than a second setting. The trigger had
  still not fired. The sharing is unchanged and now argued rather than inherited: the count's scope
  is stated beside the field in `config_reply.py`, in the orchestrator module doc's
  `ReplyBoundsConfig` entry and in the GPU runbook's per-request budget section, each pointing a
  deployment that wants two counts at `CORTEX_REASONING_BUDGET` and `CORTEX_REASONING_BUDGET_BRAIN`.
  The second env field is declined for the reason it was deferred, a setting for a case no
  deployment has reached. Recorded in ADR-0049.
