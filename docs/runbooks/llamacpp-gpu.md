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
  ADR-0004). Pick a cortex candidate from ADR-0004 to start (the 9B leaves more KV
  headroom than the 12B).

## Configure (host env / a `.env` beside the compose files)

| Variable | Meaning | Example |
|---|---|---|
| `CORTEX_MODELS_DIR` | host dir holding the GGUFs, mounted read-only | `./models` |
| `CORTEX_MODEL_FILE_CORTEX` | cortex GGUF path **relative to that dir** (LM Studio nests it under `publisher/repo/`) | `unsloth/Qwen3.5-9B-GGUF/Qwen3.5-9B-Q4_K_M.gguf` |
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
  `docker-credential-desktop.exe` (→ `exec format error` on pull). Point `DOCKER_CONFIG` at
  a config without a `credsStore` (public images pull anonymously):
  ```
  mkdir -p ~/.docker-nohelper && echo '{}' > ~/.docker-nohelper/config.json
  export DOCKER_CONFIG=~/.docker-nohelper
  ```
  (Same footgun the WSL dev runbook notes for `just up`.)

## Bring it up

```
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
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

## Measured so far (2026-06-29, 24 GB card, 16K ctx, single slot, full offload)

`nvidia-smi` total used with the model resident (only the llama-server on the GPU). Load
times were under a **55 W travel-power cap** (not the 175 W brick). VRAM is power-
independent, load/throughput are not. Full detail + placement strategy in the
[ADR-0004 addendum](../adr/ADR-0004-model-lineup.md).

| Tier | Candidate | Quant | Weights only | + vision (mmproj) | Load (55 W) |
|---|---|---|---|---|---|
| Cortex | Qwen3.5-9B | Q4_K_M | 9.2 GB | 11.0 GB (F32 proj) | ~32-42 s |
| Cortex (alt) | gemma-4-12B | q4_0 (qat) | 11.0 GB | 11.3 GB (small proj) | ~38-52 s |
| Subagent | _tbd (Slice 7)_ | | | | |
| Brain | _tbd (Slice 11)_ | | | | |
| Embedder | _tbd (Slice 5, CPU)_ | | | | |

- **Both multimodal cortex options ≈ 11 GB**, so VRAM does not decide the pick; choose on
  capability/vision quality. ~11 GB leaves ~13 GB of 24 GB for a co-resident 2-4B subagent
  (the 12 GB target in ROADMAP assumption 1 is relaxed, per the ADR-0004 addendum).
- **Placement:** embedder → CPU (`CORTEX_NGL=0`), subagents → GPU when headroom allows
  else CPU/hybrid, brain → hybrid if it doesn't fit. All per-`llama-server` flags, no core
  change (ADR-0004 addendum).
- **Swap latency (ROADMAP assumption 2):** load is ~mount-read bound (~150-180 MB/s off
  the Windows bind mount). If it dominates once swap lands (Slice 11), mirror hot models
  into a WSL-side/volume cache and re-measure.
- **Final per-tier picks:** still open (VRAM doesn't force it). Once chosen, set
  `CORTEX_MODEL_FILE_CORTEX` and note them in [ADR-0004](../adr/ADR-0004-model-lineup.md).
- **Pin the image:** replace the `ghcr.io/ggml-org/llama.cpp:server-cuda` tag in
  `docker-compose.gpu.yml` with a digest once a working version is settled (ADR-0006:
  mutable tags are a supply-chain risk).

## Teardown

```
docker compose -f docker-compose.yml -f docker-compose.gpu.yml down
```
