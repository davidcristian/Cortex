# Prose cites an engine build that nothing pins

**Status:** open, fix when it bites
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
