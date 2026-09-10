# Only one endpoint in one mode records its engine build

**Status:** open, a seam or port change comes first
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-09-10
**Trigger:** the next change that opens the model host's `HealthProbe` or `InferenceEvent`, either of which is where a build reading for the remaining endpoints would land.

Opened 2026-09-10 by the close of
[R-611](611-nothing-reads-the-build-the-engine-names-on-every-response.md), which gave a running
stack its first build reading and covered one endpoint with it.

`PropsVisionProbe.can_see` reads `build_info` off the `/props` body it already parses and puts it on
`vision probe answered` as `build`. That probe is built only for `CORTEX_VISION=auto`
(`build_vision` in [vision.py](../../../brain/packages/orchestrator/src/cortex_orchestrator/vision.py)
returns no probe for `on` and none at all for `off`), and it asks one address, `config.endpoint`.
So three populations still record nothing. A deployment that fixed the vision answer by hand logs
no build. The subagent servers and the deep model are other endpoints, and nothing asks them
anything outside a turn. And a capture decision's line says which build answered that probe rather
than which build produced a given completion, which is the half a log line cannot reach at all.

**What would close it.** Two routes, and each begins with a port change, which is why this waits
rather than being picked up behind an unchanged one.

The model host is the placement that covers every tier: it starts one `llama-server` child per
logical model and polls each child's `/health` until it serves, so the moment a child turns READY
is the moment its build could be read once and logged. `HealthProbe.serving` returns a boolean over
`GET /health` ([probe.py](../../../brain/packages/model_manager/src/cortex_model_manager/probe.py)),
so a build reading there is a widened port answer plus a second request against `/props`, and the
supervisor rather than the probe would decide when to spend it, a load being polled for minutes.

The other route is per-completion provenance: a `system_fingerprint` arm on `InferenceEvent`, read
in [decode.py](../../../brain/packages/inference/src/cortex_inference/decode.py), which reads
`timings` and `choices` off a chunk and drops the rest. That is the only shape under which a
measured figure carries the build that produced it rather than the build a probe found nearby, and
it is a contract change: the port, the fake, the contract test and the seam's own wording.

## Trail

- 2026-09-10: opened by the close of
  [R-611](611-nothing-reads-the-build-the-engine-names-on-every-response.md), recorded in the
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) addendum on the vision probe's build field,
  which argues why the reading landed on the one endpoint it did and names the three places it
  leaves unrecorded.
