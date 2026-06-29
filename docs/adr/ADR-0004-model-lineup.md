# ADR-0004: Model lineup (candidates locked)

- **Status:** Accepted (candidate sets locked by the user, 2026-06-29; final per-tier
  pick happens in Slice 4 with measured VRAM)
- **Date:** 2026-06-29

## Context

Three tiers share the 24 GB GPU (ADR-0001); cortex + embedder + one subagent must fit in
12 GB, and the cortex must be natively multimodal (vision). The user has downloaded the
candidates locally via LM Studio to `D:\Software\AI Models` (Windows; the drive is not
mounted into WSL).

## Decision on candidate sets (verbatim)

| Tier | Candidates |
|---|---|
| **Cortex** | `gemma-4-12B-it-qat-q4_0-gguf` · `Qwen3.5-9B-GGUF (Q4_K_M)` |
| **Subagents** | `gemma-4-E2B-it-qat-q4_0-gguf` · `gemma-4-E4B-it-qat-q4_0-gguf` · `Qwen3.5-0.8B-GGUF (Q8_0/BF16)` · `Qwen3.5-2B-GGUF (Q4_K_M)` · `Qwen3.5-4B-GGUF (Q4_K_M)` |
| **Brain** | `Qwen3.6-27B-GGUF (Q4_K_M)` · `Qwen3.6-35B-A3B-GGUF (UD-Q3_K_M)` · `gemma-4-31B-it-qat-q4_0-gguf` · `gemma-4-26B-A4B-it-qat-q4_0-gguf` |
| **Embedder** | `nomic-embed-text-v1.5-GGUF (Q8_0/F16)` · `nomic-embed-text-v2-moe-GGUF (Q4_K_M/Q8_0/F16)` (added 2026-06-29) |

MTP (multi-token-prediction) variants of some models exist locally but are deferred because
they use more memory; revisit only if latency demands it.

## Implications

1. **Engine question is RESOLVED.** Every artifact is GGUF (llama.cpp's native format).
   The maintainer chose llama.cpp over vLLM on 2026-06-29:
   [ADR-0005](ADR-0005-llamacpp-engine.md). Slice 4 now only measures (VRAM fit incl.
   KV + vision tower, swap latency) to make the final per-tier picks.
2. **Logical model ids, not file paths.** The core and config speak tier-logical ids
   (`cortex`, `subagent`, `brain`); only the inference adapter maps ids to artifact
   paths. File paths never enter the core.
3. **Model access without copying.** Models stay in `D:\Software\AI Models`. The
   inference container bind-mounts that directory via Docker Desktop (Windows paths work
   natively in compose on this setup); WSL never needs the files unless the
   swap-latency fallback in ADR-0005 kicks in and hot models get mirrored into a
   WSL-side/volume cache. If direct host-side/WSL access becomes necessary (e.g. a
   non-dockerized engine), enable the `/mnt/d` automount then.
4. **Envelope sanity (to verify in Slice 4).** Rough Q4 weight sizes: 12B ≈ 7 GB,
   9B ≈ 5.5 GB (cortex) + embedder (the nomic candidates are small, ~0.1-1 GB
   depending on quant; the v2-moe F16 sits at the top of that range) +
   2-4B subagent (~1.5-2.5 GB) + KV. The 12 GB envelope is plausible but tight with
   the 12B cortex; the 9B leaves more headroom. Brain candidates (~15-18 GB) all fit
   alone in 24 GB. The cortex pick must ship its vision tower and its VRAM cost counts
   against the envelope.

## Addendum (2026-06-29): local data locations

- **Models** stay in `D:\Software\AI Models` (read-only bind mount into the inference
  container, decision 3 above).
- **The knowledge base**, the durable stores behind `MemoryStore` (Postgres/pgvector),
  keeps its data under `D:\Software\AI Database`, bind-mounted, so the user can
  carry/back up/plug the knowledge base into a future setup as plain files.
  **Caveat to validate when the memory slice lands:** Postgres data directories over
  Docker-Desktop Windows bind mounts have known ownership/latency pitfalls; if the
  bind mount fails validation, the fallback is a named volume as the live data dir
  plus an automated dump/sync job into `D:\Software\AI Database`. The plug-and-play
  requirement stands either way, recorded in ROADMAP Slice 5.

## Consequences

- Slice 4's runbook (`docs/runbooks/llamacpp-gpu.md` per ADR-0005) records the
  measured numbers and the final per-tier picks.
- Config gains per-tier model-id settings with the logical defaults; the adapter maps
  them to artifacts.
