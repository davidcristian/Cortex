# The trace budget probe runs once per boot and is never repeated

**Status:** done 2026-09-12
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

`CORTEX_INFERENCE_TRACE_LEVER=auto` asks the endpoint one question at wiring and hands the answer to
`LlamaCppBackend` as a `bool`. The vision probe beside it is the deliberate contrast: it is asked
again on every advertisement and every call, because a model host can drop a projector under a brain
that never restarts. A build's support for the key cannot change that way, so this one is cached.
What can change is which build is behind the endpoint, and the compose stack names llama.cpp by
mutable tags, so an operator who pulls a newer image and recreates the model host has moved the
correct answer without touching the brain.

The direction of the staleness is the safe one. A brain that booted before the key existed goes on
sending the request it always sent, which costs a capability rather than corrupting anything; the
opposite sends a key that is ignored with nothing reported, which is where this repo already was.
Both are fixed by a restart, and `CORTEX_INFERENCE_TRACE_LEVER=on` fixes the first without one. A
probe per call was priced and refused: it adds a round trip to every completion and decodes a token
on the servers that most need not to.

## History

- 2026-08-29: opened by the close of
  [R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md), which cached the answer on the
  argument that it describes a build and left the case where the build is replaced under a running
  brain.
- 2026-09-07: checked against the tree and a real server, and not fired, though its first half has
  happened once. The mutable tag really does move here: a reading of 2026-08-29 names
  `ghcr.io/ggml-org/llama.cpp:server` at `b10666-4e97ac86e`, the cached image under that tag reports
  `b10680-d7bd3bfca` today, and a fixed `:server-cuda-b10666` copy sits beside it. The rest did not
  happen: no brain and no model host is running on this machine, so nothing was left running across
  a recreate. Asked the GPU runbook's own question, `b10680-d7bd3bfca` answered `400` naming
  `reasoning_budget_tokens`, which is what `b10666-4e97ac86e` answered on 2026-08-29, so across the
  one bump this host has taken the correct answer did not move.
- 2026-09-12: closed as the documented repair. The GPU runbook's request-budget section now has a
  paragraph saying to restart the brain after pulling llama.cpp, which direction of staleness each
  skipped restart costs, and that the brain is the stale half when the boot line and the `curl`
  disagree. Both mutable tags cached on this host still report build `b10680` at revision
  `d7bd3bfca`, read off each image's own `org.opencontainers.image.version` and `.revision` labels
  rather than by starting a server, so no pull has moved either tag since 2026-09-07. That label
  reading is now printed in the runbook: it says which build is behind a tag while a measurement is
  using the card, which the `curl` cannot do. The other half, asking again at a boundary that
  already exists, is [R-648](648-nothing-re-asks-the-trace-lever-when-the-engine-moves.md).
