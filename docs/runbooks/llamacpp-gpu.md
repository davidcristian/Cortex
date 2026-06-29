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
| `CORTEX_MODEL_FILE_CORTEX` | the cortex GGUF filename inside that dir | `Qwen3.5-9B-Q4_K_M.gguf` |

The brain-side logical id stays `CORTEX_MODEL_CORTEX=cortex` (ADR-0004); the adapter never
sees the filename. Only the compose `llama-cortex` service does.

## Bring it up

```
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

This starts `llama-cortex` (one `llama-server`, all layers on the GPU via `-ngl 99`) and
flips the brain to `CORTEX_INFERENCE_BACKEND=llamacpp` pointed at `http://llama-cortex:8080`
(ADR-0007 d4/d5). The brain waits for the model to finish loading (the service healthcheck).

- **If the healthcheck never goes healthy:** the `server-cuda` image may ship without
  `curl`. Swap the healthcheck test for `wget -qO- http://127.0.0.1:8080/health` or a
  small `python -c` poke, or check `docker compose logs llama-cortex` for the load line.
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

## Measure and record (fill these in)

Read VRAM from `nvidia-smi` with the model resident and a turn in flight (KV grows with
context). The envelope is cortex + embedder + one 2-4B subagent ≤ 12 GB (ADR-0004 §4,
ROADMAP assumption 1).

| Tier | Candidate | Quant | Weights (GB) | +KV @ ctx (GB) | Load time (s) | Verdict |
|---|---|---|---|---|---|---|
| Cortex | _tbd_ | | | | | |
| Cortex (alt) | _tbd_ | | | | | |
| Subagent | _tbd_ | | | | | |
| Brain | _tbd_ | | | | | |
| Embedder | _tbd_ | | | | | |

- **Swap latency (ROADMAP assumption 2):** load time above is process-start + GGUF read
  off the Windows bind mount. If it dominates, mirror hot models into a WSL-side/volume
  cache and re-measure. Record the decision here.
- **Final per-tier picks:** once chosen, write them into
  [ADR-0004](../adr/ADR-0004-model-lineup.md) (its Status says the final pick happens
  here) and set `CORTEX_MODEL_FILE_CORTEX` accordingly.
- **Pin the image:** replace the `ghcr.io/ggml-org/llama.cpp:server-cuda` tag in
  `docker-compose.gpu.yml` with a digest once a working version is found (ADR-0006:
  mutable tags are a supply-chain risk).

## Teardown

```
docker compose -f docker-compose.yml -f docker-compose.gpu.yml down
```
