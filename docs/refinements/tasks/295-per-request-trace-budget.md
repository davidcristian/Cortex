# One tier still has one thinking budget

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** a llama.cpp build that reads a thinking budget off the request body, or a second
caller on one tier whose right budget is a different positive count from the first's.

Opened 2026-08-17 by the trace-budget landing
([ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) trace-budget addendum), which gave the thinking
dial its middle and could only fit it per server.

`CORTEX_REASONING_BUDGET` is a flag on a tier's `llama-server`, so every request that tier serves
thinks under the same count. That covers the cases this repo has, because the passes whose
deliberation is thrown away unread already say so per request and get a trace of zero: the history
fold, the session title and the recall rank all send `thinking=False`, and a budget of any size
leaves them alone (measured: 0 characters of trace under a tier budget of 128). What it cannot
express is two positive budgets on one tier, so a deployment that wants a short think for a user's
reply and a long one for the deep phase can only get it by putting those on different tiers, which
they already are.

The engine is what holds this shut, and it was measured in both directions rather than assumed: a
request carrying `reasoning_budget: 128` was ignored on an unbudgeted server, and one carrying
`reasoning_budget: -1`, at the top level and inside `chat_template_kwargs` alike, did not lift a
budgeted server's own count. So the fix is not a field this repo can add. When a build reads it off
the body, the change is small and the shape is already there: `GenerationBounds` gains a third
number, `build_payload` renders it, and the tier flag becomes the deployment's default rather than
its only setting.
