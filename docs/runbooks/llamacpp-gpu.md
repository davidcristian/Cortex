# Runbook: llama.cpp on the GPU

Start the real cortex model on the card and check that it serves. CI never runs any of this,
because CI has no GPU. Background: [ADR-0005](../adr/ADR-0005-llamacpp-engine.md) (the engine),
[ADR-0007](../adr/ADR-0007-model-manager-inference.md) (the wiring),
[ADR-0004](../adr/ADR-0004-model-lineup.md) (the candidates and where the files live). Two
runbooks beside this one measure the stack it brings up,
[inference-measurements.md](inference-measurements.md) and
[injection-probes.md](injection-probes.md).

## Prerequisites

- Docker Desktop on Windows with the NVIDIA container toolkit or WSL GPU support enabled.
  `docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi` must list the GPU.
- The cortex GGUF present under the models directory (default `./models`). The cortex model is
  gemma-4-12B (QAT Q4) and it is the compose default; `CORTEX_MODEL_FILE_CORTEX` points the stack
  at another candidate.

## Configure

Set these in the host environment or in a `.env` file beside the compose files.

| Variable | Meaning | Example |
|---|---|---|
| `CORTEX_MODELS_DIR` | host directory holding the GGUFs, mounted read-only | `./models` |
| `CORTEX_MODEL_FILE_CORTEX` | cortex GGUF path relative to that directory (LM Studio nests it under `publisher/repo/`) | `google/gemma-4-12B-it-qat-q4_0-gguf/gemma-4-12b-it-qat-q4_0.gguf` |
| `CORTEX_MODEL_FILE_CORTEX_MMPROJ` | the multimodal projector, relative to the same directory. Setting it adds llama.cpp's `--mmproj` pair to the cortex tier's argv, which makes `GET /props` report `modalities.vision` and makes the brain offer `capture_screen` (ADR-0029). Empty (the default) starts text-only. See [vision.md](vision.md) | `google/gemma-4-12B-it-qat-q4_0-gguf/mmproj-gemma-4-12b-it-qat-q4_0.gguf` |
| `CORTEX_IMAGE_MAX_TOKENS` | how many tokens one picture may occupy, and with it how much of a 4K screen the cortex can read. `1024` is the default, paired with `CORTEX_BODY_CAPTURE_MAX_EDGE=2048` on the brain; `0` hands the budget back to the model, which reads 13% of a 4K screen. Never set llama.cpp's `--image-max-tokens` by hand instead. See [inference-measurements.md](inference-measurements.md) | `1024` |
| `CORTEX_CTX_SIZE` | context window (KV size). Set it: the model default of 262144 alone uses about 8 GB | `16384` |
| `CORTEX_REPLY_THINKING` | keeps the model's deliberation on for a user's own reply. `false` skips it and shortens the wait rather than the answer: 11.8 to 18.1 s before the first word with it on, 0.4 s with it off for an answer of the same size. It costs answer quality on hard questions and empties the thinking status the overlay shows. `false` is a request to the model's chat template, not a guarantee, so check your model first (see [inference-measurements.md](inference-measurements.md)) | `true` |
| `CORTEX_REPLY_MAX_TOKENS` | caps how far each completion of a user's turn decodes. `0` sends no cap and leaves the context window as the bound. Never set this against an unbounded trace: a reasoning model spends its budget on thinking first, and `max_tokens: 512` with thinking on returned an empty reply 3 of 3 on this model. Pair it with a `CORTEX_REASONING_BUDGET` that leaves room to answer, or with `CORTEX_REPLY_THINKING=false` once you know the model obeys it. Whatever cuts a reply, the turn says so under the text | `0` |
| `CORTEX_REASONING_BUDGET` | how many tokens the cortex tier may spend thinking before the engine closes the thought and makes it answer. `-1` (the default) emits no flag and leaves the trace unbounded; `0` ends every thought immediately; `N > 0` is a token budget | `-1` |
| `CORTEX_REASONING_BUDGET_BRAIN` | the same setting for the deep tier, separate because the cortex answers while somebody waits and the deep model was chosen for reaching an answer inside its trace (ADR-0004) | `-1` |
| `CORTEX_REPLY_TRACE_TOKENS` | how many tokens a user's own reply may spend thinking, sent on the request rather than fixed on the tier (ADR-0049). Unset (the default) leaves `CORTEX_REASONING_BUDGET` deciding; `0` ends the thought at once and a positive count bounds it. Needs an engine that reads the key, which `CORTEX_INFERENCE_TRACE_LEVER` decides | unset |
| `CORTEX_INFERENCE_TRACE_LEVER` | whether a request may include its own trace budget. `auto` asks the endpoint one model-free question at boot and uses the answer; `on` and `off` decide it directly. See "A budget per request" below | `auto` |
| `CORTEX_NGL` | GPU layers to offload: `99` = all, `0` = CPU only, anything between is hybrid | `99` |
| `CORTEX_INFERENCE_STALL_TIMEOUT_S` | on the brain: how long a resident or deep tier stream may send nothing before the turn fails. It bounds the gap between chunks, never the length of a generation, so a long answer is never cut off. Size it above the worst legitimate time to first token. The default clears the 17.5 s a contended cortex took here, with room for the deep tier (ADR-0005) | `120` |

The brain-side model id stays `CORTEX_MODEL_CORTEX=cortex`; the adapter never sees the filename.
Only the `model-host` sidecar does, and that is where these variables are read
([model-swap.md](model-swap.md), [brain-model-manager.md](../modules/brain-model-manager.md)).

## Running compose from WSL when automount and interop are off

The compose default `CORTEX_MODELS_DIR` is the Windows path (`D:\Software\AI\Models`), which
Docker Desktop mounts natively when compose runs from PowerShell. Driving compose from a WSL
distro with `automount=false` and `interop=false` needs two one-time steps. First, expose the
models to the distro: binding Docker Desktop's internal `/run/desktop/mnt/host/...` path does not
reliably serve file contents, so mount the folder over drvfs instead. Second, `docker` cannot run
the Windows `docker-credential-desktop.exe` with interop off, so point `DOCKER_CONFIG` at a config
with no `credsStore`; public images pull anonymously.

```
sudo mkdir -p /srv && sudo mount -t drvfs 'D:\Software\AI' /srv
export CORTEX_MODELS_DIR=/srv/models          # persist via /etc/fstab if you like
mkdir -p ~/.docker-nohelper && echo '{}' > ~/.docker-nohelper/config.json
export DOCKER_CONFIG=~/.docker-nohelper
```

A native `dockerd` inside the distro (docker context `default` on `/var/run/docker.sock`, not
Docker Desktop) also needs the GPU toolkit installed in the distro, or `--gpus all` and compose
`deploy.reservations.devices` fail with `could not select device driver "nvidia" [[gpu]]`. Install
it with `sudo apt-get install -y nvidia-container-toolkit`, then
`sudo nvidia-ctk runtime configure --runtime=docker` and `sudo service docker restart`; a Docker
update without a PC restart can also break this. To verify, `docker info` shows
`Runtimes: … cdi: nvidia.com/gpu=all`, and
`docker run --rm --gpus all --entrypoint nvidia-smi ghcr.io/ggml-org/llama.cpp:server-cuda -L`
lists the GPU. Docker Desktop from PowerShell bridges the GPU for you; a WSL dockerd does not.

## Bring it up

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml up --build
```

This starts `model-host`, the supervisor sidecar, which spawns one `llama-server` child for the
cortex tier with every layer on the GPU (`-ngl 99`), and points the brain at
`http://model-host:8080` with `CORTEX_INFERENCE_BACKEND=llamacpp`. The sidecar replaced the
always-on `llama-cortex` service so a swap can stop the cortex and start the deep model, which no
compose service can do (ADR-0030).

The sidecar's healthcheck asks whether the cortex tier is READY, not whether the daemon answers,
so the brain waits for the model to finish loading. Watch `docker compose logs model-host` for
the `listening on http` line; children inherit the daemon's streams, so both appear in that log.
Then check from the host: `curl -s http://127.0.0.1:8080/v1/models`.

## Run the integration test

With the server up:

```
cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 \
  CORTEX_MODEL_CORTEX=cortex \
  uv run pytest -m integration --no-cov packages/inference
```

`--no-cov` is required, or the workspace's 100% coverage threshold fails the run. This streams a
real completion through `LlamaCppBackend` and asserts the output is not empty. It also runs
`test_reasoning_model_emits_reasoning_before_reply`: given a reasoning-inducing prompt, the cortex
streams `reasoning_content`, which the adapter turns into a `ReasoningChunk`. Validated 2026-07-06,
and the same day the whole path was driven through `TurnEngine`, 326 events on that prompt.

## A budget per request, where the engine reads one

A recent llama.cpp reads a trace budget off the request as
`reasoning_budget_tokens`, falling back to the tier's flag where the request names none. It is a
sampler that watches for the thought's start sequence and forces its end tag, so it also works on
a request constrained by a `response_format`, where `enable_thinking` alone does not. The recap
fold, the session title and the recall rank each send
`reasoning_budget_tokens: 0` where this deployment's engine reads one, since their deliberation is
thrown away unread. A user's own reply does not, because its trace is the thinking status the
overlay shows; set that one with `CORTEX_REPLY_TRACE_TOKENS`, which covers both the cortex turn
and the deep phase a handoff continues it with. To bound those two traces differently, use
`CORTEX_REASONING_BUDGET` and `CORTEX_REASONING_BUDGET_BRAIN` and leave
`CORTEX_REPLY_TRACE_TOKENS` unset.

The key is sent only where the engine reads it, because a build that does not implement it
ignores it without error. `CORTEX_INFERENCE_TRACE_LEVER=auto` asks the endpoint one question at
boot. Ask it yourself with:

```
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"cortex","messages":[{"role":"user","content":"."}],"max_tokens":1,"reasoning_budget_tokens":-2}'
```

`400` is a build that parses the key and rejected the out-of-range value. `200` is a build that
does not implement it and answered the completion. Measured 2026-08-29, same model and prompt one
minute apart: `b10666-4e97ac86e` answered `400` naming the field and `b9870-2d973636e` answered
`200`, and each behaved as its own answer predicted. The brain logs its answer at boot:

```
INFO:cortex_inference.trace_probe:trace lever probe answered endpoint=<the endpoint asked> lever=<true or false>
```

A server that could not be reached logs `trace lever probe failed` at `WARNING`. When the answer
is no and `CORTEX_REPLY_TRACE_TOKENS` is set, the count is not sent and the brain says so once, on
the first reply that would have included it:

```
WARNING:cortex_inference.backend:trace budget not sent because the trace lever is off model=<the model asked> trace_budget=<the count>
```

Fix it by unsetting the count, by setting `CORTEX_INFERENCE_TRACE_LEVER=on` on a build you know
reads the key, or by restarting the brain against a build whose probe answers `lever=true`.
Restart the brain after pulling a newer llama.cpp: the answer is asked once and kept for the life
of the brain process, and neither direction of that staleness is reported. If the boot line and
the `curl` above disagree, the brain is the stale half. Read which build a tag points at:

```
docker image inspect ghcr.io/ggml-org/llama.cpp:server-cuda \
  --format '{{index .Config.Labels "org.opencontainers.image.version"}} {{index .Config.Labels "org.opencontainers.image.revision"}}'
```

The version label plus the first nine characters of the revision label make the build id, so both
mutable tags cached on this host read as `b10680-d7bd3bfca` (2026-09-12).

## The two settings that decide how much of a screen the cortex reads

Left to itself the model picks its own per-image budget, 266 prompt tokens for any capture from
1280 px up, which on a 4K desktop reads 6 to 8 of 47 ground-truth strings. Two settings raise it,
they only work together, and both are the default:

```
CORTEX_IMAGE_MAX_TOKENS=1024    # on the model-host sidecar (the table above)
CORTEX_BODY_CAPTURE_MAX_EDGE=2048    # on the brain (docs/runbooks/vision.md)
```

At the default that reads 36 to 38 of 47 strings for about 400 MiB more VRAM, 0.6 s more time to
first token and 744 more context tokens per capture. `CORTEX_IMAGE_MAX_TOKENS=0` hands the budget
back to the model and drops both flags from the child's argv; `CORTEX_BODY_CAPTURE_MAX_EDGE=0`
returns the body to its own 1600 px default. The full table, the legibility boundary by type size
and the byte costs are in [vision capture](../readings/vision-capture.md); the procedure that
re-runs them is in [inference-measurements.md](inference-measurements.md).

Four things to know before changing either.

- **Raising one alone does little.** The budget alone leaves the body sending
  a 1600 px picture (24 to 26 of 47); the capture edge alone sends pixels into an encoder that
  throws them away (4 of 47 at 2048 px and at 3072 px, no better than the
  1600 px default).
- **Do not send the whole screen.** A 3840 px capture at the same 1010 tokens reads worse than a
  2048 px one, 30 against 36 to 38, because the encoder's internal resize is a poorer filter than
  the body's box average. Downscale to the budget.
- **Never set llama.cpp's `--image-max-tokens` by hand.** A budget over the engine's 512
  micro-batch default aborts `llama-server` inside `llama_decode` on the first oversized picture
  (`GGML_ASSERT`, SIGSEGV, container exit 139, no error reply, vision gone for the session).
  `CORTEX_IMAGE_MAX_TOKENS` emits the matching `--ubatch-size` for that reason. The abort also
  depends on the build: a cached `server-cuda` at b9870 survived what b10236 and b10276 abort on.
- **Small type needs a window, not a bigger budget.** 15 px type on an unscaled monitor stays at
  4 of 16 at every budget tried, while pointing the capture at a window takes it to 9 or 10 of 12.
  The window must be inside `CORTEX_BODY_CAPTURE_MAX_EDGE`, and the crop cannot see anything
  outside the window. The model makes that choice per call through `capture_screen`'s `target`.

A 4K frame at 2048 px costs 243 KB as a text desktop and 4.67 MB with heavy film grain over it,
74% of the 6 MiB ceiling; only per-pixel uniform noise fires the halving ladder (dropping the
capture to
1024 px, below even the 1600 px view). The costliest realistic display is 2560x1440, at 79%.

## What fits on the card

VRAM is `nvidia-smi` total used with the model resident. The two cortex load times were taken
with the card held to about a third of its full power; VRAM does not depend on power, load times
do. Conditions and the full per-candidate tables: [model lineup](../readings/model-lineup.md),
[two tiers on one card](../readings/co-residency.md).

| Tier | Candidate | Quant | Weights only | + vision (mmproj) | Load |
|---|---|---|---|---|---|
| **Cortex (pick)** | **gemma-4-12B** | q4_0 (QAT) | 11.0 GB | 11.3 GB (small proj) | ~38-52 s |
| Cortex (alternate) | Qwen3.5-9B | Q4_K_M | 9.2 GB | 11.0 GB (F32 proj) | ~32-42 s |
| Subagent (pick) | **gemma-4-E4B** (CPU) | q4_0 (QAT) | 4.9 GB, ~2.5 GiB RSS | n/a | 38 s |
| Subagent (override) | Qwen3.5-2B (CPU) | Q4_K_M | 1.19 GB, ~893 MiB RSS | n/a | ~14.5 s |
| **Brain (pick)** | **gemma-4-31B** | q4_0 (QAT) | 18.7 GB (8K ctx) | n/a | 99.6 s |
| Brain (alternate) | Qwen3.6-27B | Q4_K_M | 16.1 GB (8K ctx) | n/a | 109.5 s |
| Embedder (pick) | **nomic-embed-text-v1.5** (CPU) | Q8_0 | 0.146 GB, ~18 MiB RSS | n/a | ~1.2 s |

The two cortex rows and the embedder are 2026-06-29, both subagent rows 2026-07-03, and the two
brain rows 2026-08-04 through the `model-host` sidecar with the cortex evicted first at
`CORTEX_CTX_SIZE_BRAIN=8192` and `-ngl 99`. Every row but the two cortex ones was taken with no
power cap, so those load times do not compare. The mount now holds only a `UD-Q4_K_XL` and a
`Q8_0` of Qwen3.5-9B, so runs of that candidate since 2026-09-06 load
`unsloth/Qwen3.5-9B-GGUF/Qwen3.5-9B-UD-Q4_K_XL.gguf`.

The VRAM budget is a deliberate 14 GB soft cap (`CORTEX_VRAM_SOFT_CAP_GB`), leaving about 10 GB
of the 24 GB card for a second monitor and games. The cortex reservation is 8.6 GiB, so 5.4 GiB
of headroom is left, which holds exactly one 3.5 GiB subagent request. Placement is cortex on the
GPU, embedder on the CPU (`CORTEX_NGL=0`), subagents into a pool the cortex sizes within budget,
deep model hybrid if it does not fit, all as per-`llama-server` flags. A GPU placement decision is
not a GPU process: `CORTEX_SUBAGENTS_GPU_ENDPOINT` still defaults to the CPU server, so a stack
that has not named `CORTEX_MODEL_FILE_SUBAGENT_GPU` and repointed that endpoint runs a GPU-placed
spawn on the CPU server. The three settings to change are listed in
`docker/docker-compose.gpu.yml`; the procedure is [subagents-cpu.md](subagents-cpu.md) section 2c.

The cortex and the deep model do not both fit: 29139 MiB wanted against 24463. The pair still
reports `ready`, because WSL2 pages the overcommit, and the deep model's decode falls to 14.80 to
17.29 tok/s. Memory readings cannot tell a fit from a spill; decode can, and the procedure is in
[model-swap.md](model-swap.md). Swap time is dominated by reading the mount, about 150 to
180 MB/s off the Windows bind mount, against 0.1 to 0.4 s from SIGTERM to a reaped child.

To reproduce a VRAM reservation reading, publish the control API (`just up-modelhost-loopback`),
read the child's real argv out of `/proc` rather than off the compose file, and sample
`nvidia-smi --query-gpu=memory.used` every 0.2 to 0.3 s while stopping, starting and driving the
tier. Per-process attribution (`nvidia-smi --query-compute-apps`) reports nothing under WSL2, so
total used minus a floor read at both ends of the run is the only instrument available.

## Teardown

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml down
```
