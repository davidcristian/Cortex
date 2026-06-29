# ADR-0005: llama.cpp as the inference engine

- **Status:** Accepted (design decision, 2026-06-29; supersedes ADR-0001 decision 4's
  choice of vLLM)
- **Date:** 2026-06-29

## Context

ADR-0004 locked the model candidates. All are GGUF artifacts downloaded via LM Studio.
vLLM's GGUF support is experimental and per-architecture, and the founding vLLM choice
carried a class of consumer-hardware quirks (SM120/FP8 config, FlashInfer, the
CUDA-graph-capture hang on WSL2) that needed a dedicated runbook. This is a consumer
program on a consumer GPU, not a throughput-serving deployment.

## Decision

1. **llama.cpp is the engine behind `InferenceBackend`.** Native GGUF (the artifacts
   run as downloaded), first-class CUDA on consumer GPUs, none of the vLLM/WSL2 quirk
   class. The planned `blackwell-vllm.md` runbook is replaced by `llamacpp-gpu.md`
   (written in Slice 4).
2. **Serving shape: one `llama-server` process per loaded model**, its
   OpenAI-compatible HTTP API as the adapter surface (chat completions + embeddings).
   The `InferenceBackend` adapter is a thin HTTP client and is fakeable in tests like every
   other adapter.
3. **The Model Manager's swap mechanism is process lifecycle.** Load = start a
   `llama-server` on the artifact; unload = stop the process. This makes the hard rule
   literal: a swap kills the serving process outright, so anything not in the external
   store is gone by construction. That is exactly the discipline the architecture already
   enforces. The lease/queue design from ADR-0001 is unchanged.
4. **Embeddings run on the same engine** (nomic-embed GGUF candidates, ADR-0004): one
   engine for all tiers plus the embedder, one VRAM accounting model (per-process).
5. **GPU deployment stays dockerized** via the NVIDIA container toolkit in the
   `docker-compose.gpu.yml` override (pinned llama.cpp CUDA server image or build),
   with models bind-mounted read-only from `D:\Software\AI Models` (ADR-0004).
6. **Portability improves.** llama.cpp runs Metal and CPU: the future macOS move can
   likely reuse this same adapter against a Metal build (the second portability seam in
   AGENTS.md/ARCHITECTURE.md; the new MLX adapter ADR-0001 d4 anticipated is likely
   unnecessary), and a CPU build enables local GPU-less experiments. CI remains
   inference-free regardless.

## Consequences

- vLLM-specific text in ADR-0001, AGENTS.md, ARCHITECTURE.md, and ROADMAP.md is
  updated; ADR-0001 d4 carries a supersession note.
- vLLM's continuous batching / paged-attention throughput is given up. It is irrelevant for
  a single user; llama.cpp's single-stream latency is what matters here.
- Swap latency is now dominated by process start + GGUF load from the bind-mounted
  Windows drive; if that mount is slow, hot models get mirrored into a WSL-side cache
  (measured in Slice 4, per ROADMAP assumption 2).
- llama.cpp flags/versions are adapter + runbook concerns; the core never sees them.
