# The trace lever is answered once per boot and never re-asked

**Status:** landed 2026-09-12
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

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
older one, sends a key that is ignored with nothing reporting it, which is exactly where this repo already
was.
Both are fixed by a restart, and `CORTEX_INFERENCE_TRACE_LEVER=on` fixes the first without one. The
cost of the alternative is real and was priced: a probe per call adds a round trip to every
completion and decodes a token on the servers that most need not to.

**What closed it.** The second of the two repairs this entry offered: a paragraph in the GPU
runbook's own lever section saying to restart the brain after pulling llama.cpp, which direction of
staleness each skipped restart costs, and that the brain is the stale half when the boot line and
the `curl` disagree. The first, a re-ask on a boundary that already exists, is the seam half and is
[R-648](648-nothing-re-asks-the-trace-lever-when-the-engine-moves.md), deferred there on the
argument this entry opened with: a probe per call is priced and refused, and the swap boundary is
worth a re-ask only once somebody is bitten.

## Trail

- 2026-08-29: opened by the close of
  [R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md), which cached the lever's
  answer on the argument that it describes a binary and left the case where the binary is replaced
  under a running brain.
- 2026-09-07: the trigger was held to the tree and to a real server, and it has **not** fired,
  though its first half has happened once. The mutable tag really does move here: a reading of
  2026-08-29 names `ghcr.io/ggml-org/llama.cpp:server` at `b10666-4e97ac86e`, the cached image
  under that tag reports `b10680-d7bd3bfca` today, and a pinned `:server-cuda-b10666` copy sits
  beside it on the same host. The rest of the trigger did not happen. No brain and no model host is
  running on this machine, so nothing was left running across a recreate, and the cached images are
  the two the ADR-0005 engine-tag addendum read on 2026-09-04, so no pull has happened since; the
  registry has moved on again in the meantime, `server-cuda` now resolving to `sha256:84a9f771dfcb`
  and `server` to `sha256:ef50b81ee57e`. The staleness the entry is about needs more than a bump,
  and that is what the narrowing above says: asked the GPU runbook's own lever question tonight,
  `b10680-d7bd3bfca` answered `400` naming `reasoning_budget_tokens`, which is the answer
  `b10666-4e97ac86e` gave on 2026-08-29, so across the one bump this host has taken the honest
  answer did not move. The runbook line the entry proposes is still unwritten and still the cheap
  half.
- 2026-09-12: **landed**, as the documented repair. The GPU runbook's request-lever section now
  carries the restart paragraph, and the trigger is answered once more without having fired. Both
  mutable tags cached on this host still report build `b10680` at revision `d7bd3bfca`, read off
  each image's own `org.opencontainers.image.version` and `.revision` labels rather than by starting
  a server, so no pull has moved either tag since 2026-09-07 and the pinned `:server-cuda-b10666`
  copy is unchanged beside them. That label reading is the cheap half of this entry's own question
  and the runbook now prints it: it says which build is behind a tag while a measurement is using
  the card, which the `curl` cannot do. The running container tonight is one live harness's server
  on the CUDA tag, not a brain and not a model host, so again nothing was left running across a
  recreate. The seam half moves to
  [R-648](648-nothing-re-asks-the-trace-lever-when-the-engine-moves.md).
