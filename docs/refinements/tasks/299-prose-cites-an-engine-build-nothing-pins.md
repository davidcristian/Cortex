# Prose cites an engine build that nothing pins

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** the first measurement that contradicts a recorded one, or the first behaviour a reader cannot reproduce, on a stack whose engine build has moved under the number the prose names.

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
