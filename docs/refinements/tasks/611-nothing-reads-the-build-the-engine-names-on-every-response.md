# Nothing reads the build the engine names on every response

**Status:** landed 2026-09-10
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-09-08 by the close of
[R-299](299-prose-cites-an-engine-build-nothing-pins.md), which repaired five citations by hand and
found the field that would have made repairing them unnecessary.

llama-server names its own build on everything it answers. Every chunk of a stream and every
non-streaming completion carries `system_fingerprint`, and `/props` reports the same string as
`build_info`. Measured 2026-09-08 on `ghcr.io/ggml-org/llama.cpp:server`, the shipped subagent pick
at `-ngl 0`: both read `b10680-d7bd3bfca`, and all seven chunks of one streamed completion carried
the field. That is the same spelling the corpus already quotes, `b10298-15586e2d7`, which was itself
read off `system_fingerprint` on 2026-08-08 rather than off any `--version`.

No code here reads the field off a response. `system_fingerprint` is named only in prose, in three
docstrings that date a reading of it and in the ADR and module pages that quote a build, and
`decode.py` reads `timings` and `choices` off a chunk and drops the rest. Two things do ask
`/props`, and neither puts a build in a running stack's record. `PropsVisionProbe` asks it at the
cortex endpoint on every capture decision, reads `modalities.vision` alone, and drops `build_info`
out of the body it has already parsed. The thinking-switch live harness reads `build_info` and
`model_path` off `/props` and writes both into the sample `just switch-tail` publishes, which is one
hand-run reading of one server
([R-528](528-a-switch-sample-names-the-model-the-operator-typed-and-no-engine-build.md)). So every
figure this stack produces outside that sample is attributed to a build by hand, in prose, by
whoever was watching, and a figure whose sentence is not updated goes on naming a build that has not
run here for weeks. Five such sentences were repaired on the day this was filed, and the repair is a
claim about the past that the next reader cannot check.

**Why this is not the tag question.** Pinning `ghcr.io/ggml-org/llama.cpp:server` and
`:server-cuda` by digest decides which build runs, which is a deployment choice and is deliberately
left open (ADR-0005 build-provenance addendum). Reading the fingerprint decides whether a
measurement says which build produced it, and is true whether or not anything is pinned. The two
are independent, and this is the half that does not change what the stack starts.

**What would close it.** Two places already talk to the engine outside a turn and log what they
hear, and a build reading belongs at one of them. The trace lever probe asks a question whose
answer is a property of the binary rather than of the model, but it asks it once, at
`config.endpoint`, and only in `auto` mode, so a deployment that set the lever by hand probes
nothing. The vision probe asks `GET /props` at that same endpoint on every capture decision and
already parses the body `build_info` sits in, so reading it there is a second key off a body the
process is holding and a second field on a line it already writes. Either way a stack should say in
its own log which engine each endpoint it talks to is running before anything is measured against
it, which the switch-tail harness's `/props` read shows costs one request and two asserted fields.
A port arm on
`InferenceEvent` is the larger alternative and reaches per-completion provenance, which the log line
does not; it is a contract change, so it needs the fake, the contract test and the seam's own
wording, and this entry does not choose between them. Either way a runbook stops asking an operator
to remember which build they were on.

**What closed it: the vision probe's `/props` read, which was already parsing the body.**
`PropsVisionProbe.can_see` now takes `build_info` off the same body it reads `modalities.vision`
out of and puts it on `vision probe answered` as `build`, so the line carries the endpoint, the
verdict and the engine that gave it. The vision runbook shows the rendered line, which puts the
field list under `samplecheck.py`. A body naming no build renders `build=None` rather than losing
the line, on the same tolerant reading the verdict is taken under.

The other two candidates were weighed and neither was refused outright. The trace-lever probe asks
once at the composition root, which is the better cadence, but a build that parses the key answers
400 and that body carries no fingerprint, so it would need a second request to learn anything. A
`system_fingerprint` arm on `InferenceEvent` is still the only shape under which a measured figure
carries the build that produced it, and it is a contract change. What the entry left unweighed is
the model host's readiness probe, which covers every tier rather than one endpoint and would have
been the better home if it were not a boolean over `GET /health`: a build there is a port change
plus a second request per poll.

The reading covers one endpoint in one mode, and the residue is filed on its own terms as
[R-622](622-only-one-endpoint-in-one-mode-records-its-engine-build.md): a deployment that fixed
`CORTEX_VISION` by hand records nothing, the subagent servers and the deep model are never asked,
and a capture decision's line says which build answered that probe rather than which build produced
a completion.

## Trail

- 2026-09-08: opened by the close of
  [R-299](299-prose-cites-an-engine-build-nothing-pins.md), recorded in the
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) build-provenance addendum, which measured the
  two fields above and repaired the five prose citations that this would have made unnecessary.
- 2026-09-09: claims held to the tree, and two of the three negative ones were wrong the day they
  were written. `system_fingerprint` is spelled in three Python docstrings and several documents
  here, though no code reads it, and `/props` is asked twice: by `PropsVisionProbe` on every
  capture decision, which reads `modalities.vision` and drops the build, and by the thinking-switch
  live harness, which has read `build_info` into its sample since 2026-09-02. What survives is the
  entry's subject, that no path a running stack takes records the build. The closing paragraph
  described the trace lever probe as model-free and per endpoint, where it names the cortex model,
  runs once against one endpoint, and runs at all only in `auto`.
- 2026-09-10: landed on the vision probe. `PropsVisionProbe.can_see`
  ([vision.py](../../../brain/packages/orchestrator/src/cortex_orchestrator/vision.py)) reads
  `build_info` off the `/props` body it already parses and renders it as `build`; the rendered line
  is in [the vision runbook](../../runbooks/vision.md), the contract in
  [brain-orchestrator.md](../../modules/brain-orchestrator.md), and the reasoning, the three
  rejected placements and the mutation table in the
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) addendum on the vision probe's build field.
  Opened [R-622](622-only-one-endpoint-in-one-mode-records-its-engine-build.md).
