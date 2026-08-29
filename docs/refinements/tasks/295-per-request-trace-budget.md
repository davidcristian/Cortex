# One tier still has one thinking budget

**Status:** landed 2026-08-29
**Area:** inference-model-manager
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
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

**The engine half of that trigger has fired, measured 2026-08-28 on
`ghcr.io/ggml-org/llama.cpp` `b10644-d7a207411`.** The server reads `reasoning_budget_tokens` (or
`thinking_budget_tokens`) off the request body and falls back to the tier's flag only when the
request says `-1`. The paragraph above is still right about the name it sent: `reasoning_budget` is
ignored on that same build in the same minute, logged as `tokens=-1` on every draw. So what is left
open here is the second half of the trigger, two callers on one tier wanting different positive
counts, and the engine no longer holds it shut. [R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md)
is the other use of the same key, a zero rather than a count, and carries the questions a payload
key raises for both.

**Landed with it, as the [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) request-lever
addendum.** The shape this entry predicted is the shape that shipped, unchanged: `GenerationBounds`
gained a third number, `build_payload` renders it, and the tier flag became the deployment's
default rather than its only setting, since the engine falls back to `--reasoning-budget` exactly
where a request names no count. The second half of the trigger, two callers on one tier wanting
different positive counts, is now expressible: the fold, the title and the recall rank each send a
zero and a user's reply sends whatever `CORTEX_REPLY_TRACE_TOKENS` names, all on the one resident
cortex.

Measured per request on one unbudgeted server, so the dial is the engine's rather than a claim
about it: unbounded spent 591 to 854 characters of trace and returned **nothing** inside a cap of
256, `reasoning_budget_tokens: 128` spent 310 to 516 and returned an answer, and `32` spent 0 to 92
and returned a longer one. What the addendum adds beyond this entry's own design is the floor under
the key, since a build that does not know it ignores it in silence
([R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md) is where those questions were
recorded).

## Trail

- 2026-08-29: landed as the ADR-0005 request-lever addendum, carried by the close of
  [R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md), the two being one key on one
  payload read twice. The engine half of the trigger had fired the day before; the shape shipped is
  the one this entry described, with a probe of the running engine added under it because a build
  that does not read the key says nothing. The residue is on that entry's own trail:
  [R-495](495-the-forced-thought-can-leak-its-own-start-tag.md),
  [R-496](496-the-trace-lever-is-answered-once-per-boot.md),
  [R-497](497-nothing-reports-a-trace-budget-that-went-unread.md) and
  [R-498](498-one-reply-trace-budget-for-two-tiers.md).
