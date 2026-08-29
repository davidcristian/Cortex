# The trace lever is answered once per boot and never re-asked

**Status:** open, fix when it bites
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** a llama.cpp image upgraded under a brain that keeps running, which is a
`docker compose pull` followed by a recreate of the model host alone.

Opened 2026-08-29 by the close of
[R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md), whose decision 5 argues that
the answer may be cached because it describes a binary, and which is the sentence this entry holds
open.

`CORTEX_INFERENCE_TRACE_LEVER=auto` asks the endpoint one question at wiring and hands the answer
to `LlamaCppBackend` as a `bool`. The vision probe beside it is the deliberate contrast: it is
re-asked on every advertisement and every call, because a model host can drop a projector under a
brain that never restarts and the argv is what its answer describes. A binary cannot change that
way, so this one is cached. What can change is which binary is behind the endpoint, and the compose
stack names llama.cpp by mutable tags, so an operator who pulls a newer image and recreates the
model host has moved the honest answer without touching the brain.

**Why it was left.** The direction of the staleness is the safe one. A brain that booted before the
key existed goes on sending the request it always sent, which costs a capability rather than
corrupting anything; the opposite, a brain that booted against a knowing build and now talks to an
older one, sends a key that is ignored in silence, which is exactly where this repo already was.
Both are fixed by a restart, and `CORTEX_INFERENCE_TRACE_LEVER=on` fixes the first without one. The
cost of the alternative is real and was priced: a probe per call adds a round trip to every
completion and decodes a token on the servers that most need not to.

**What would close it.** Either a cheap re-ask on a boundary that already exists, the model swap
being the obvious one since the residency scope knows a child was replaced, or a line in the
`llamacpp-gpu.md` upgrade path saying to restart the brain after pulling llama.cpp. The second is
a paragraph and the first is a seam, so the second should probably land first and the first only
if somebody is bitten.

## Trail

- 2026-08-29: opened by the close of
  [R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md), which cached the lever's
  answer on the argument that it describes a binary and left the case where the binary is replaced
  under a running brain.
