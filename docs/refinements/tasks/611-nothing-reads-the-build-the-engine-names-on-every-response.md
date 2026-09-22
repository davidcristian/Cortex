# Nothing reads the build the engine names on every response

**Status:** done 2026-09-10
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

llama-server reports its own build on everything it returns: `system_fingerprint` on every stream
chunk and every non-streaming completion, and the same string as `build_info` from `/props`.
Measured 2026-09-08 on `ghcr.io/ggml-org/llama.cpp:server` with the shipped subagent pick at
`-ngl 0`, both read `b10680-d7bd3bfca`, and all seven chunks of one streamed completion included the
field.

No code here read that field. It appeared only in prose, and `decode.py` reads `timings` and
`choices` off a chunk and drops the rest. Two callers asked `/props` and neither recorded a build
from a running stack: `PropsVisionProbe` read `modalities.vision` and dropped `build_info`, and the
thinking-switch harness wrote both fields into the sample `just switch-tail` publishes, which is one
hand-run reading of one server. So every other figure was attributed to a build by hand, in prose,
and five such sentences had just been repaired by hand when this was filed.

This is not the image-tag question. Fixing `ghcr.io/ggml-org/llama.cpp:server` and `:server-cuda` by
digest decides which build runs and is deliberately left open (ADR-0005 decision 8); reading the
fingerprint decides whether a measurement says which build produced it.

**What closed it.** `PropsVisionProbe.can_see` now takes `build_info` off the same `/props` body it
reads `modalities.vision` from and puts it on the `vision probe answered` line as `build`, so the
line has the endpoint, the result and the engine that gave it. A body with no build renders
`build=None` rather than losing the line. The vision runbook shows the rendered line, which puts the
field list under `samplecheck.py`.

Two other placements were weighed. The trace-setting probe runs once at the composition root, which
is the better moment, but a build that parses the key answers 400 with no fingerprint in the body,
so it would need a second request. A `system_fingerprint` field on `InferenceEvent` is the only
design under which a measured figure includes the build that produced it, and it is a contract
change needing the fake, the contract test and the proto wording. The model host's readiness probe
covers every tier rather than one endpoint and would have been the better home if it were not a
boolean over `GET /health`.

The remaining narrower problem is
[R-622](622-only-one-endpoint-in-one-mode-records-its-engine-build.md).

## History

- 2026-09-08: opened by the close of
  [R-299](299-prose-names-an-engine-build-that-no-tag-keeps-fixed.md), recorded in
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) decision 8. That session measured the two fields
  above and repaired the five prose citations.
- 2026-09-09: claims checked, and two of the three negative ones were wrong when written.
  `system_fingerprint` appears in three Python docstrings and several documents, and `/props` is
  asked twice, by `PropsVisionProbe` on every capture decision and by the thinking-switch harness,
  which has read `build_info` into its sample since 2026-09-02. What survives is the subject: no
  path a running stack takes records the build.
- 2026-09-10: done, on the vision probe. `PropsVisionProbe.can_see`
  ([vision.py](../../../brain/packages/orchestrator/src/cortex_orchestrator/vision.py)) reads
  `build_info` off the `/props` body it already parses and renders it as `build`. The rendered line
  is in [the vision runbook](../../runbooks/vision.md), the contract in
  [brain-orchestrator.md](../../modules/brain-orchestrator.md), and the reasoning and the three
  rejected placements in [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) decision 9. Opened
  [R-622](622-only-one-endpoint-in-one-mode-records-its-engine-build.md).
