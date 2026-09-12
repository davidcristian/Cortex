# Nothing re-asks the trace lever when the engine behind the endpoint moves

**Status:** open, fix when it bites
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-09-12
**Trigger:** a newer llama.cpp pulled under a brain that keeps running, where the new build answers
the lever question differently from the answer that brain cached and the documented restart was
skipped, which shows as the GPU runbook's own `curl` contradicting the brain's boot line.

Opened 2026-09-12 by the close of
[R-496](496-the-trace-lever-is-answered-once-per-boot.md), which landed the documented repair, a
restart after the pull, and left the seam half of its two options here.

`resolve_trace_lever` is called once, inside `build_inference_backend`, and its answer reaches
`LlamaCppBackend` as a `bool` that lives as long as the process. The vision probe beside it is the
deliberate contrast, re-asked on every advertisement and every call because a projector is an argv a
model host can change under a brain that never restarts. A binary cannot change that way, which is
the argument for caching this one; what can change is which binary is behind the endpoint, and the
compose stack names llama.cpp by mutable tags.

**Why the obvious boundary is weaker than it looks.** The boundary named when this was deferred is
the model swap, on the ground that `SwappingModelManager.swap_scope` already knows a child was
replaced. Two things narrow it. That scope exists only with `CORTEX_ESCALATION` on, which is off by
default, so the shipped stack has no boundary after boot at all. And a swap starts another child of
the same image, so the answer re-asked there is the same answer unless the image moved under the
sidecar in the meantime, which is a `docker compose pull` and a recreate the brain never observes. A
re-ask in the swap scope therefore catches this only on an escalating stack whose next handoff
happens to fall after a pull.

**Why it was left.** The direction of the staleness is the safe one, and both directions are fixed by
a restart the GPU runbook now prints. A brain that booted before the key existed goes on sending the
request it always sent, which costs it the lever; a brain that booted against a build that reads the
key and now talks to one that does not sends a key the engine drops without reporting anything. The
alternative was priced when the lever was designed: a probe per call adds a round trip to every
completion and decodes a token on the servers that most need not to.

**What would close it.** A re-ask on a boundary that already exists, the swap scope's swap-in being
the only candidate and reaching only the escalating case; or a re-ask on a schedule, which is the
probe-per-call cost spread thinner and still a token on a busy server; or the accepting answer, that
a documented restart is the repair and the cached `bool` stays. The third is what landed, so anything
built here has to argue against it with a deployment that was actually bitten.

## Trail

- 2026-09-12: opened by the close of
  [R-496](496-the-trace-lever-is-answered-once-per-boot.md), whose runbook paragraph is the cheap
  half of that entry's two repairs. The narrowing above is new: the swap boundary the older entry
  called obvious is absent from the default stack and blind to the recreate that causes the
  staleness, so what remains is smaller than it read.
