# Nothing asks the trace setting again when the engine behind the endpoint moves

**Status:** open, waiting for its trigger
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)
**Verified:** 2026-09-19
**Trigger:** a newer llama.cpp pulled under a brain that keeps running, where the new build answers
the trace question differently from the answer that brain cached and the documented restart was
skipped, which shows as the GPU runbook's own `curl` contradicting the brain's boot line.

`resolve_send_trace_budget` is called once, inside `build_inference_backend`, and its answer reaches
`LlamaCppBackend` as a `bool` that lives as long as the process. The vision probe beside it is the
deliberate contrast, asked again on every advertisement and every call, because a projector is an
argv a model host can change under a brain that never restarts. A binary cannot change that way,
which is the argument for caching this answer; what can change is which binary is behind the
endpoint, and the compose stack names llama.cpp by mutable tags.

**Why the obvious boundary is weaker than it looks.** The boundary named when this was deferred is
the model swap, because `SwappingModelManager.swap_scope` already knows a child was replaced. Two
things narrow it. That scope exists only with `CORTEX_ESCALATION` on, which is off by default, so
the shipped stack has no boundary after boot at all. And a swap starts another child of the same
image, so the answer would be the same answer unless the image moved under the sidecar in the
meantime, which is a `docker compose pull` and a recreate the brain never observes.

**Why it was left.** The direction of the staleness is the safe one, and both directions are fixed
by a restart the GPU runbook prints. A brain that booted before the key existed goes on sending the
request it always sent, which costs it the setting; a brain that booted against a build that reads
the key and now talks to one that does not sends a key the engine drops silently. The alternative
was priced when the setting was designed: a probe per call adds a round trip to every completion and
decodes a token on the servers that most need not to.

**What would close it.** Asking again on a boundary that already exists, the swap scope being the
only candidate and reaching only the escalating case; or asking again on a schedule, which is the
probe-per-call cost spread thinner and still a token on a busy server; or keeping the cached `bool`
with the documented restart as the repair. The third is what was decided, so anything built here has
to argue against it with a deployment that actually hit the problem.

## History

- 2026-09-12: opened by the close of
  [R-496](496-the-trace-budget-probe-runs-once-per-boot-and-is-never-repeated.md), which made the documented repair, a
  restart after the pull, and left this half. The narrowing above is new: the swap boundary that
  entry called obvious is absent from the default stack and blind to the recreate that causes the
  staleness.
- 2026-09-14: the trigger has not fired, taken as the reading it names rather than reasoned about.
  Both mutable tags this stack names still resolve to the build the GPU runbook recorded on
  2026-09-12, `b10680-d7bd3bfca` for `ghcr.io/ggml-org/llama.cpp:server` and for `:server-cuda`,
  read with the runbook's own `docker image inspect` command. `resolve_send_trace_budget` is still called
  once inside `build_inference_backend`, `CORTEX_ESCALATION` is still off by default, and the
  documented restart is still what the runbook prints. This is not the same defect as the entry
  about a budget that went unread: that one asks for the cached answer to be reported, this one for
  it to be asked again.
- 2026-09-19: the trigger has not fired and every claim checked out unchanged. The runbook's label
  command still reads `b10680 d7bd3bfca` off both cached tags, at the digests `sha256:952424b09abc`
  (`server-cuda`) and `sha256:db057ec90de0` (`server`), and no brain container runs on this host, so
  there is no boot line for a `curl` to contradict. `resolve_send_trace_budget` is still called once in
  `build_inference_backend`'s llama.cpp branch; the vision answer is still asked again per
  advertisement and per call (`cortex_orchestrator/vision.py`); `SwappingModelManager.swap_scope` is
  still the only boundary after boot. The one change nearby is in the entry about a budget that went
  unread, which now names a third place a dropped count could be reported; that place reports the
  cached answer and does not ask it again.
