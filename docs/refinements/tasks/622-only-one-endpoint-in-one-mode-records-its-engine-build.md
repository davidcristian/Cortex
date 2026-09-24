# Only one endpoint in one mode records its engine build

**Status:** done 2026-09-24
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

`PropsVisionProbe.can_see` reads `build_info` off the `/props` body it already parses and puts it on
`vision probe answered` as `build`. That probe is built only for `CORTEX_VISION=auto`
(`build_vision` in
[vision.py](../../../brain/packages/orchestrator/src/cortex_orchestrator/vision.py) returns no probe
for `on`, and none at all for `off` or for a brain with no body wired), and it asks one address,
`config.endpoint`. Three cases therefore record nothing: a deployment that fixed the vision
answer by hand, the subagent servers and the deep model, which nothing asks anything outside a turn,
and any given completion, since a capture decision's line says which build answered that probe
rather than which build produced a reply.

**What would close it.** Two routes, and each starts with a port change, which is why this waits.

The model host covers every tier: it starts one `llama-server` child per logical model and polls
each child's `/health` until it serves, so the moment a child turns READY is the moment its build
could be read once and logged. `HealthProbe.serving` returns a boolean over `GET /health`
([probe.py](../../../brain/packages/model_manager/src/cortex_model_manager/probe.py)), so a build
reading there is a widened port return plus a second request against `/props`, and the supervisor
rather than the probe would decide when to spend it, a load being polled for minutes.

The other route is per-completion provenance: a `system_fingerprint` field on `InferenceEvent`,
read in [decode.py](../../../brain/packages/inference/src/cortex_inference/decode.py), which reads
`timings` and `choices` off a chunk and drops the rest. That is the only design under which a
measured figure includes the build that produced it rather than the build a probe found nearby, and
it is a contract change: the port, the fake, the contract test and the proto's own wording.

## History

- 2026-09-10: opened by the close of
  [R-611](611-nothing-reads-the-build-the-engine-names-on-every-response.md), recorded in
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) decision 9, which explains why the reading went
  on the one endpoint it did and names the three places it leaves unrecorded.
- 2026-09-17: checked again, not fired. Neither path has a commit since 2026-09-10; both last
  changed on 2026-08-31, and the two model-host commits since then (the subagent prompt cache) did
  not touch the probe. `PropsVisionProbe.can_see` still logs `build` on `vision probe answered`,
  and nothing else in `brain/packages/*/src` reads `build_info` or `system_fingerprint`. One
  correction: `build_vision` also returns no probe when no body is wired, since without a body
  there is no capture tool to ask about.
- 2026-09-24: done by neither route, in the inference adapter with no port change. Read off a CPU
  `server` container on `b10680-d7bd3bfca`: every streamed chunk names the build as
  `system_fingerprint`, the same string as `/props` `build_info`, and `/health` names none.
  `LlamaCppBackend` now logs `model now served by engine build` the first time a model names a build
  and whenever that changes, for every generation tier in every vision mode at no request. One claim
  was wrong: the model host supervises the GPU tiers only, so its route would have missed the CPU
  subagent servers. The `InferenceEvent` route would pass a value no core decision reads, and no
  readings record uses a per-completion build: each names its session's build off `/props` or the
  image labels. Recorded in [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) decision 9 and
  [subagents-cpu.md](../../runbooks/subagents-cpu.md). Opened
  [R-721](721-the-embedders-engine-build-is-recorded-nowhere.md).
