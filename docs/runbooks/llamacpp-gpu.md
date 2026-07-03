# Runbook for llama.cpp on the GPU (Slice 4 host half)

Bring up the real cortex model and measure it. This is the **host-driven** half of Slice
4: the CI half (the adapter, the Model Manager, the compose override) is built and gated;
here you run it against the GPU, record the numbers, and lock the final per-tier picks.
Engine rationale: [ADR-0005](../adr/ADR-0005-llamacpp-engine.md); wiring:
[ADR-0007](../adr/ADR-0007-model-manager-inference.md); candidates + data locations:
[ADR-0004](../adr/ADR-0004-model-lineup.md). CI never runs any of this (GPU-less by
design, AGENTS.md gate 3).

## Prerequisites

- Docker Desktop on Windows with the **NVIDIA container toolkit** / WSL GPU support
  enabled (`docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi`
  should list the GPU).
- The cortex GGUF present under the models dir (default `./models`,
  ADR-0004). The chosen cortex is **gemma-4-12B** (QAT Q4 per the ADR-0004 addendum), the compose
  default; `CORTEX_MODEL_FILE_CORTEX` overrides it to try another candidate.

## Configure (host env / a `.env` beside the compose files)

| Variable | Meaning | Example |
|---|---|---|
| `CORTEX_MODELS_DIR` | host dir holding the GGUFs, mounted read-only | `./models` |
| `CORTEX_MODEL_FILE_CORTEX` | cortex GGUF path **relative to that dir** (LM Studio nests it under `publisher/repo/`); default is the gemma-4-12B pick | `google/gemma-4-12B-it-qat-q4_0-gguf/gemma-4-12b-it-qat-q4_0.gguf` |
| `CORTEX_CTX_SIZE` | context window (KV size); **set it**. The model default (262144) alone eats ~8 GB | `16384` |
| `CORTEX_NGL` | GPU layers to offload: `99` = all, `0` = CPU-only, partial = hybrid (ADR-0004 addendum) | `99` |

The brain-side logical id stays `CORTEX_MODEL_CORTEX=cortex` (ADR-0004); the adapter never
sees the filename. Only the compose `llama-cortex` service does.

## Running from WSL (when automount/interop are off)

The compose default `CORTEX_MODELS_DIR` is the **Windows** path (`D:\Software\AI\Models`),
which Docker Desktop bind-mounts natively when you run compose from **PowerShell**. If you
drive compose from a **WSL** distro with `automount=false` / `interop=false` (as this repo's
dev distro is set), two one-time steps are needed:

- **Expose the models to the distro.** Binding Docker Desktop's internal
  `/run/desktop/mnt/host/...` path does *not* reliably serve file contents; mount the AI
  folder via drvfs instead and point `CORTEX_MODELS_DIR` at it:
  ```
  sudo mkdir -p /srv && sudo mount -t drvfs 'D:\Software\AI' /srv
  export CORTEX_MODELS_DIR=/srv/models          # persist via /etc/fstab if you like
  ```
- **Credential helper.** With interop off, `docker` can't exec the Windows
  `docker-credential-desktop.exe` (→ `exec format error` / `executable not found` on pull).
  Point `DOCKER_CONFIG` at a config without a `credsStore` (public images pull anonymously):
  ```
  mkdir -p ~/.docker-nohelper && echo '{}' > ~/.docker-nohelper/config.json
  export DOCKER_CONFIG=~/.docker-nohelper
  ```
  (Same footgun the WSL dev runbook notes for `just up`.)
- **The GPU toolkit is needed when `docker` is a *native* `dockerd` in the distro** (context
  `default → /var/run/docker.sock`, not Docker Desktop). Then `--gpus all` and compose
  `deploy.reservations.devices` fail with `could not select device driver "nvidia" [[gpu]]`
  until the NVIDIA Container Toolkit is installed **in the distro** and wired into the daemon:
  ```
  sudo apt-get install -y nvidia-container-toolkit
  sudo nvidia-ctk runtime configure --runtime=docker
  sudo service docker restart          # a Docker update without a PC restart can also break this
  ```
  Verify: `docker info` shows `Runtimes: … cdi: nvidia.com/gpu=all`, and
  `docker run --rm --gpus all --entrypoint nvidia-smi ghcr.io/ggml-org/llama.cpp:server-cuda -L`
  lists the GPU. (Docker Desktop from PowerShell bridges the GPU for you; a native WSL dockerd
  does not.)

## Bring it up

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml up --build
```

This starts `llama-cortex` (one `llama-server`, all layers on the GPU via `-ngl 99`) and
flips the brain to `CORTEX_INFERENCE_BACKEND=llamacpp` pointed at `http://llama-cortex:8080`
(ADR-0007 d4/d5). The brain waits for the model to finish loading (the service healthcheck).

- **Healthcheck:** the current `server-cuda` image ships `curl` (not `wget`), so the
  compose healthcheck works as-is; it goes healthy once the model finishes loading. If a
  future image drops `curl`, swap the test for a `python -c` poke or watch
  `docker compose logs llama-cortex` for the `listening on http` line.
- **Sanity poke from the host** (loopback publish is on `127.0.0.1:8080`):
  `curl -s http://127.0.0.1:8080/v1/models`.

## Run the integration test

With the server up:

```
cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 \
  CORTEX_MODEL_CORTEX=cortex \
  uv run pytest -m integration --no-cov packages/inference
```

`--no-cov` matters. The 100% gate in the workspace addopts would otherwise fail the run
(the same convention as the Redis live test). This streams a real completion through
`LlamaCppBackend` and asserts non-empty output.

## Framing-efficacy probe (Slice 6.5 / ADR-0013, agent-runnable)

Confirms the prompt-injection **framing** actually changes the cortex's behavior. This is the model
observation CI can't make. Bring up **only** the model on GPU (no brain build); `--jinja` (so
gemma's tool chat-template renders) is baked into the GPU compose since 2026-07-03 (ADR-0009
addendum, though at probe time it still needed a scratch override):

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml \
  up -d llama-cortex     # 127.0.0.1:8080, ~9.8 GB VRAM, healthy in ~10 s
```

Then probe `/v1/chat/completions` directly, building messages with the **shipped** constants
(`from cortex_core import SECURITY_PREAMBLE, wrap_untrusted`): a `system` = `SECURITY_PREAMBLE`, the
user ask, an assistant `read_file` tool-call, and a `tool` message whose content is
`wrap_untrusted(<injection payload>)` (exactly what the brain produces). Compare against an
unframed control (no preamble, raw payload). **gemma-4-12B is a reasoning model**, so give it
`max_tokens≈1500` and read `reasoning_content` (not just `content`), or it hits the length cap
mid-think and returns empty. Result (2026-07-01): the framed model cites the preamble in its
reasoning to defeat every injection variant. See the [ADR-0013 addendum](../adr/ADR-0013-untrusted-content.md).

## Measured so far (2026-06-29, 24 GB card, 16K ctx, single slot, full offload)

`nvidia-smi` total used with the model resident (only the llama-server on the GPU). Load
times were under a **55 W travel-power cap** (not the 175 W brick). VRAM is power-
independent, load/throughput are not. Full detail + placement strategy in the
[ADR-0004 addendum](../adr/ADR-0004-model-lineup.md).

| Tier | Candidate | Quant | Weights only | + vision (mmproj) | Load (55 W) |
|---|---|---|---|---|---|
| **Cortex (pick)** | **gemma-4-12B** | q4_0 (QAT) | 11.0 GB | 11.3 GB (small proj) | ~38-52 s |
| Cortex (alt) | Qwen3.5-9B | Q4_K_M | 9.2 GB | 11.0 GB (F32 proj) | ~32-42 s |
| Subagent | _tbd (Slice 7, CPU)_ | | | | |
| Brain | _tbd (Slice 11)_ | | | | |
| Embedder | _tbd (Slice 5, CPU)_ | | | | |

- **Cortex = gemma-4-12B** (stronger chat model + QAT). Both candidates ≈ 11 GB, so VRAM
  didn't decide it. The budget is a **deliberate 14 GB soft cap** (env
  `CORTEX_VRAM_SOFT_CAP_GB`; the user keeps ~10 GB of 24 GB for a second monitor + gaming),
  so the ~11.3 GB cortex sits under it with ~2.7 GB headroom. The embedder and subagents
  still run on **CPU** (ADR-0004 addendum, not a relaxed envelope).
- **Placement:** cortex → GPU (~11.3 GB, ~2.7 GB under the 14 GB cap), embedder → CPU (`CORTEX_NGL=0`),
  subagents → CPU (a dynamic pool the cortex sizes within budget), brain → hybrid if it
  doesn't fit. All per-`llama-server` flags, no core change (ADR-0004 addendum).
- **Swap latency (ROADMAP assumption 2):** load is ~mount-read bound (~150-180 MB/s off
  the Windows bind mount). If it dominates once swap lands (Slice 11), mirror hot models
  into a WSL-side/volume cache and re-measure.
- **Remaining picks:** cortex is settled (gemma-4-12B, the compose default). Subagent sizes
  (Slice 7), brain (Slice 11), and embedder quant (Slice 5) follow, recorded in
  [ADR-0004](../adr/ADR-0004-model-lineup.md) as each lands.
- **Pin the image:** replace the `ghcr.io/ggml-org/llama.cpp:server-cuda` tag in
  `docker/docker-compose.gpu.yml` with a digest once a working version is settled (ADR-0006:
  mutable tags are a supply-chain risk).

## Teardown

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml down
```
