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

MTP (multi-token-prediction) variants of some models exist locally but are deferred because
they use more memory; revisit only if latency demands it.

## Implications

1. **Engine question (resolved in Slice 4).** Every artifact is GGUF, which is llama.cpp's
   native format. vLLM's GGUF support is experimental and per-architecture, so Slice 4
   evaluates: vLLM-with-GGUF vs. a **llama.cpp-server adapter** behind `InferenceBackend`
   vs. re-downloading vLLM-native quants (AWQ/GPTQ/FP8). The port absorbs whichever
   outcome; if the engine changes from vLLM, amend ADR-0001 decision 4 and the AGENTS.md
   summary line. Measurements (VRAM fit incl. KV + vision tower, swap latency) decide.
2. **Logical model ids, not file paths.** The core and config speak tier-logical ids
   (`cortex`, `subagent`, `brain`); only the inference adapter maps ids to artifact
   paths. File paths never enter the core.
3. **Model access without copying.** Models stay in `D:\Software\AI Models`. The
   inference container bind-mounts that directory via Docker Desktop (Windows paths work
   natively in compose on this setup); WSL never needs the files. If host-side/WSL access
   becomes necessary (e.g. a non-dockerized engine), enable the `/mnt/d` automount then.
4. **Envelope sanity (to verify in Slice 4).** Rough Q4 weight sizes: 12B ≈ 7 GB,
   9B ≈ 5.5 GB (cortex) + embedder (~1-2 GB) + 2-4B subagent (~1.5-2.5 GB) + KV. The
   12 GB envelope is plausible but tight with the 12B cortex; the 9B leaves more
   headroom. Brain candidates (~15-18 GB) all fit alone in 24 GB. The cortex pick must
   ship its vision tower and its VRAM cost counts against the envelope.

## Consequences

- Slice 4's runbook `docs/runbooks/blackwell-vllm.md` (rename it if the engine changes)
  records the measured numbers and the final per-tier picks.
- Config gains per-tier model-id settings with the logical defaults; the adapter maps
  them to artifacts.
