# No handoff on Qwen3.8-27B has sent three leading system messages

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0071](../../adr/ADR-0071-leading-system-messages.md)
**Verified:** 2026-11-21

The deep phase opens its request with up to three system messages: the security preamble, the
recalled memory when recall found something, and the recap once the history window has folded
older turns (`assemble_inference_messages` in `brain/packages/core/src/cortex_core/turn_context.py`).
Before a request with two or more, the adapter asks the leased server whether its template renders
all of them and joins them when it does not (`_joins` in
`brain/packages/inference/src/cortex_inference/backend.py`), and logs `system message probe
answered` with the endpoint, the count and the answer.

The two handoffs on the deep pick of 2026-11-21 sent one
([readings](../../readings/model-swap.md#a-handoff-on-the-deep-pick)). Their stack had no memory
store and the chat of three turns was under the history window, so the probe did not run against
the deep endpoint and the brain's log has no such line. What is known for this file on build
b12375 comes from `POST /apply-template` on the deep server alone: three leading system messages
render in order as one system block. No deep request through the brain has had a memory or a
recap in it on this model.

## What to run

The stack of [R-1268](1268-no-handoff-has-run-through-the-brain-on-qwen38-27b.md)
(`~/.cache/cortex-run/2026-11-21/h1/run.sh`) with Postgres and the embedding server up as well,
so that memory is on. One chat: store a fact the later task needs, write enough turns that the
window folds the first ones into a recap (`CORTEX_HISTORY_CHAR_BUDGET` can be lowered for the
run), then a task the cortex hands over whose answer needs the stored fact and a detail only the
recap has.

What would close it: the brain's `system message probe answered` line for
`http://model-host:8081` with `system_messages=3` and its answer, the deep reply using both the
stored fact and the recap's detail, and the record in the readings. A reply that misses either
one is a defect to file.

## History

- 2026-11-21: filed when the handoffs of R-1268 were found to have sent one leading system
  message each.
