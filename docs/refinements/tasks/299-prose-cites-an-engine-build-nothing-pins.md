# Prose cites an engine build that nothing pins

**Status:** landed 2026-09-08
**Area:** inference-model-manager
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

The trigger this entry waited on, a measurement contradicting a recorded one or a behaviour a
reader cannot reproduce on a stack whose engine build has moved under the number the prose names,
fired on 2026-09-06 and is recorded in the trail below.

Opened 2026-08-17 by an observation made while closing an unrelated entry, and recorded rather than
acted on because acting on it would change the deployed image.

**What was observed.** This repo pulls its engine by a floating tag.
`brain/Dockerfile.modelhost` builds the model host `FROM ghcr.io/ggml-org/llama.cpp:server-cuda`
and `docker/docker-compose.subagents.yml` runs `ghcr.io/ggml-org/llama.cpp:server`, neither with a
digest. Several measurements are written down against a build number instead:
`b10298-15586e2d7` in `cortex_inference/request.py`, in `cortex_inference/decode.py`, in
`inference/tests/test_cadence_contract.py`, in `docs/modules/brain-inference.md` and at the
handoff ADR, all of them about what the cortex tier's server does with `timings` and with a tool
schema. The images on this machine report something else. `llama-server --version` inside the
cached `server-cuda` prints `version: 9870 (2d973636e)`, and inside the cached `server` prints
`version: 9879 (72874f559)`. So the CPU-tier citations match the image that would run, and the
GPU-tier ones name a build this machine does not have.

**Why it is worth recording.** The number is not decoration: the same corpus already records that a
cached `server-cuda` at b9870 survives a start that b10236 and b10276 abort on (the vision ADR and
the GPU runbook), so which build is present changes behaviour and not only throughput. A reader who
re-pulls the tag gets neither the build the prose names nor necessarily the one that works, and
every figure attributed to b10298 becomes a claim about a stack nobody in the repo is running.

**Three shapes, none of them settled here.** Pinning the image by digest makes the tag mean one
thing and turns an engine upgrade into a commit, at the cost of a deliberate bump whenever upstream
fixes something this repo wants. Having the stack record what it actually ran, alongside any
measurement it produces, keeps the pull floating and moves the build number from prose to evidence,
which is where a measurement's provenance belongs; that is more machinery, and it only helps
measurements taken after it lands. Accepting the drift and striking build numbers from prose is the
cheapest and gives up the ability to say what a figure was measured against, which several of these
figures exist precisely to establish. The first two are not exclusive.

Nothing here proposes changing the deployed image, and nothing in this entry was measured against a
build other than the two named above.

**Where the number came from, which this entry did not know.** `b10298-15586e2d7` was never a
`--version` reading. It is the `system_fingerprint` llama-server puts on its own responses, read off
the running stack on 2026-08-08 while the decode cadence was designed. So the build did answer here,
in the field the prose quotes, and this entry's comparison against an image's `--version` was
comparing two different readings. Measured 2026-09-08 on `ghcr.io/ggml-org/llama.cpp:server`, the
shipped subagent pick at `-ngl 0 --jinja --ctx-size 2048 --parallel 1`: `system_fingerprint` on a
completion and `build_info` at `/props` both read `b10680-d7bd3bfca`, so the `bNNNNN` spelling the
corpus quotes is alive on the build present today and only the version string moved to
`0.3.0-dev (build 10680, commit d7bd3bfca)`. The cadence claim re-derives on it as well: one
streamed completion of seven chunks carried `timings` on exactly one, the last, unasked.

**Both cached images are unmoved and both tags have moved again.** `server-cuda` is still cached at
`sha256:952424b09abc` and `server` at `sha256:db057ec90de0`, the digests recorded on 2026-09-04, and
both report build 10680. In the registry, read with `docker manifest inspect` so nothing is pulled,
`server-cuda` now resolves to `sha256:4ae7aeb8b667` and `server` to `sha256:07cf5635844c`, which is
a third pair in five days.

**Two of the three shapes, and the third left to the maintainer.** The five citations now say when
each was read, that the build named itself in `system_fingerprint`, and what the stack starts today.
Pinning by digest is not decided here: it turns every upstream fix into a commit in this
repository, which is a deployment choice rather than a documentation repair, and nothing measured
today argues either way. The recording shape is available and unbuilt, since nothing in the tree
reads `system_fingerprint` or `/props`, and it is filed as
[R-611](611-nothing-reads-the-build-the-engine-names-on-every-response.md) because it needs a log
line at boot or a port arm rather than a sentence.

## Trail

- 2026-08-17: opened while closing an unrelated entry, recording that two floating tags carry
  several measurements written against a build number, and that the machine's own images already
  reported neither.
- 2026-09-06: **fired, on both halves of the trigger.** The builds this entry measured are gone:
  `ghcr.io/ggml-org/llama.cpp:server-cuda` and `:server` both now report
  `version: 0.3.0-dev (build 10680, commit d7bd3bfca)` on this machine, where the entry recorded
  `9870 (2d973636e)` and `9879 (72874f559)`. The version string's own format moved with them, so a
  reader parsing the old shape gets nothing. The prose still names `b10298-15586e2d7` in
  [request.py](../../../brain/packages/inference/src/cortex_inference/request.py),
  [decode.py](../../../brain/packages/inference/src/cortex_inference/decode.py),
  [test_cadence_contract.py](../../../brain/packages/inference/tests/test_cadence_contract.py),
  [brain-inference.md](../../modules/brain-inference.md) and at the handoff ADR, which is a build
  no image here has ever reported and is now two builds behind the one that would run.
- 2026-09-06: **the contradiction the trigger names is already written down**, and it was recorded
  on 2026-08-29 rather than tonight. One request carrying `reasoning_budget_tokens: -2` gets `400`
  naming the field on `b10666-4e97ac86e` and `200` with the field ignored on `b9870-2d973636e`
  ([ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) request-lever addendum,
  [brain-inference.md](../../modules/brain-inference.md), and the four worlds of
  [test_lever.py](../../../brain/packages/inference/tests/test_lever.py) built over both answers).
  One request, two builds, two behaviours. That is a measurement contradicting a recorded one on a
  stack whose engine build moved, which is the first clause of the trigger word for word.
- 2026-09-06: **the second of the three shapes is partly landed already, by other passes.**
  [subagents-cpu.md](../../runbooks/subagents-cpu.md) records a reading taken on
  `sha256:db057ec90de0a423255a218b9612420993237ff33db68b3155dc3bba9b994a20` (build
  `b10680-d7bd3bfca`), which is provenance carried as evidence rather than as prose, and the switch
  tail's two readers pin `BUILD` as a module constant. A `server-cuda-b10666` image is cached here
  beside the floating one, so a hand pin has already been reached for once. What is left is the
  choice this entry declined to make: pin the two tags by digest, or strike the build numbers from
  the prose that cannot be re-measured. It is filed as actionable because the trigger fired, not
  because a shape was chosen.
- 2026-09-06: three candidates offered with this check were held against the trigger and none of
  them is it. A withdrawn dialect reading, a falsified pixel-replication premise and a lineup table
  naming a quant an engine ADR had measured as a different one are all facts about this tree and
  this mount, not about the engine build moving under the prose. They belong to their own entries.
- 2026-09-08: **landed, on two of its three shapes, and one premise was wrong.** The build the
  prose names was read off `system_fingerprint` and not off `--version`, so the entry's own
  conclusion that no image here ever reported it was drawn from the wrong reading, and the trail
  note above saying a reader parsing the old shape gets nothing is wrong for the shape the corpus
  uses: `system_fingerprint` and `/props.build_info` still print `b10680-d7bd3bfca` on the build
  present today. The five citations now date their reading and name what the stack starts.
  Digest pinning is left to the maintainer, and the recording half is
  [R-611](611-nothing-reads-the-build-the-engine-names-on-every-response.md). Measurements and the
  registry readings: the [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) build-provenance
  addendum.
