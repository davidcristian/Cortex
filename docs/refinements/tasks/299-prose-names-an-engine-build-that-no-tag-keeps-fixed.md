# Prose names an engine build that no tag keeps fixed

**Status:** done 2026-09-08
**Area:** inference-model-manager
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-17 while closing an unrelated entry, and recorded rather than acted on because
acting on it would change the deployed image.

This repo pulls its engine by a moving tag. `brain/Dockerfile.modelhost` builds the model host
`FROM ghcr.io/ggml-org/llama.cpp:server-cuda` and `docker/docker-compose.subagents.yml` runs
`ghcr.io/ggml-org/llama.cpp:server`, neither with a digest. Several measurements are written
against a build number instead: `b10298-15586e2d7` in `cortex_inference/request.py`, in
`cortex_inference/decode.py`, in `inference/tests/test_cadence_contract.py`, in
`docs/modules/brain-inference.md` and at the handoff ADR, all about what the cortex tier's server
does with `timings` and with a tool schema.

The number matters: the same corpus records that a cached `server-cuda` at b9870 survives a start
that b10236 and b10276 abort on (the vision ADR and the GPU runbook), so which build is present
changes behaviour and not only throughput. A reader who re-pulls the tag gets neither the build the
prose names nor necessarily the one that works.

Three shapes were available. Fixing the image by digest makes the tag mean one thing and turns an
engine upgrade into a commit. Having the stack record what it ran alongside any measurement it
produces keeps the pull moving and puts the build number in evidence rather than prose, at the cost
of more machinery that only helps measurements taken after it exists. Accepting the change and
striking build numbers from prose is cheapest and gives up the ability to say what a figure was
measured against.

Where the number came from, which this entry did not know: `b10298-15586e2d7` was never a
`--version` reading. It is the `system_fingerprint` llama-server puts on its own responses, read
off the running stack on 2026-08-08 while the decode cadence was designed. So the build did answer
here, in the field the prose quotes, and this entry's comparison against an image's `--version` was
comparing two different readings. Measured 2026-09-08 on `ghcr.io/ggml-org/llama.cpp:server`, the
shipped subagent pick at `-ngl 0 --jinja --ctx-size 2048 --parallel 1`: `system_fingerprint` on a
completion and `build_info` at `/props` both read `b10680-d7bd3bfca`, so the `bNNNNN` form the
corpus quotes is alive on the build present today, and only the version string moved to
`0.3.0-dev (build 10680, commit d7bd3bfca)`. The cadence claim holds on it too: one streamed
completion of seven chunks included `timings` on exactly one, the last, unasked.

Two of the three shapes were taken. The five citations now say when each was read, that the build
named itself in `system_fingerprint`, and what the stack starts today. Fixing by digest is left to
the maintainer, because it turns every upstream fix into a commit here, which is a deployment
choice rather than a documentation repair. The recording shape is unbuilt, since nothing in the
tree reads `system_fingerprint` or `/props`, and it is filed as
[R-611](611-nothing-reads-the-build-the-engine-names-on-every-response.md).

## History

- 2026-08-17: Opened while closing an unrelated entry, recording that two moving tags serve several
  measurements written against a build number.
- 2026-09-06: Triggered, on both halves. `ghcr.io/ggml-org/llama.cpp:server-cuda` and `:server`
  both now report `version: 0.3.0-dev (build 10680, commit d7bd3bfca)` on this machine, where the
  entry recorded `9870 (2d973636e)` and `9879 (72874f559)`. The prose still named
  `b10298-15586e2d7` in five places.
- 2026-09-06: The contradiction the trigger names was already written down, on 2026-08-29. One
  request with `reasoning_budget_tokens: -2` gets `400` naming the field on `b10666-4e97ac86e`
  and `200` with the field ignored on `b9870-2d973636e`
  ([ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md),
  [brain-inference.md](../../modules/brain-inference.md), and the four worlds of
  [test_trace_probe.py](../../../brain/packages/inference/tests/test_trace_probe.py) built over both
  answers). One request, two builds, two behaviours.
- 2026-09-06: The second of the three shapes is partly done already, by other passes.
  [subagents-cpu.md](../../runbooks/subagents-cpu.md) records a reading taken on
  `sha256:db057ec90de0a423255a218b9612420993237ff33db68b3155dc3bba9b994a20` (build
  `b10680-d7bd3bfca`), which is provenance as evidence rather than as prose, and the switch tail's
  two readers hold `BUILD` as a module constant. A `server-cuda-b10666` image is cached here beside
  the moving one, so a manual fix has been reached for once.
- 2026-09-06: Three candidate triggers offered with this check were compared against it and none of
  them is it. A withdrawn dialect reading, a falsified pixel-replication premise and a lineup table
  naming a quant an engine ADR had measured as a different one are facts about this tree and this
  mount, not about the engine build moving under the prose.
- 2026-09-08: Closed on two of its three shapes, and one premise was wrong: the build the prose
  names was read off `system_fingerprint`, not off `--version`, so the conclusion that no image here
  ever reported it was drawn from the wrong reading. Both cached images are unmoved, `server-cuda`
  at `sha256:952424b09abc` and `server` at `sha256:db057ec90de0`, the digests recorded on
  2026-09-04, both reporting build 10680, while in the registry, read with `docker manifest inspect`
  so nothing is pulled, `server-cuda` resolves to `sha256:4ae7aeb8b667` and `server` to
  `sha256:07cf5635844c`, a third pair in five days. Measurements and registry readings are at
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) decision 8.
