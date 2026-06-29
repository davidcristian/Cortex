# ADR-0004: Model lineup (candidates locked)

- **Status:** Accepted (candidates locked 2026-06-29; cortex pick = **gemma-4-12B**, made
  in Slice 4 (see the measurements addendum); subagent/brain/embedder picks follow in
  Slices 7/11/5)
- **Date:** 2026-06-29

## Context

Three tiers share the 24 GB GPU (ADR-0001); the AI stack must fit under a deliberate soft
cap (**14 GB**, see the addendum), and the cortex must be natively multimodal (vision).
The user has downloaded the
candidates locally via LM Studio to `D:\Software\AI\Models` (Windows; the drive is not
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
3. **Model access without copying.** Models stay in `D:\Software\AI\Models`. The
   inference container bind-mounts that directory via Docker Desktop (Windows paths work
   natively in compose on this setup); WSL never needs the files unless the
   swap-latency fallback in ADR-0005 kicks in and hot models get mirrored into a
   WSL-side/volume cache. If direct host-side/WSL access becomes necessary (e.g. a
   non-dockerized engine), enable the `/mnt/d` automount then.
4. **Envelope sanity (to verify in Slice 4).** Rough Q4 weight sizes: 12B ≈ 7 GB,
   9B ≈ 5.5 GB (cortex) + embedder (the nomic candidates are small, ~0.1-1 GB
   depending on quant; the v2-moe F16 sits at the top of that range) +
   2-4B subagent (~1.5-2.5 GB) + KV. The 14 GB envelope is plausible but tight with
   the 12B cortex; the 9B leaves more headroom. Brain candidates (~15-18 GB) all fit
   alone in 24 GB. The cortex pick must ship its vision tower and its VRAM cost counts
   against the envelope.

## Addendum (2026-06-29): local data locations

- **Models** stay in `D:\Software\AI\Models` (read-only bind mount into the inference
  container, decision 3 above).
- **The knowledge base**, the durable stores behind `MemoryStore` (Postgres/pgvector),
  keeps its data under `D:\Software\AI\Database`, bind-mounted, so the user can
  carry/back up/plug the knowledge base into a future setup as plain files.
  **Caveat to validate when the memory slice lands:** Postgres data directories over
  Docker-Desktop Windows bind mounts have known ownership/latency pitfalls; if the
  bind mount fails validation, the fallback is a named volume as the live data dir
  plus an automated dump/sync job into `D:\Software\AI\Database`. The plug-and-play
  requirement stands either way, recorded in ROADMAP Slice 5.

## Consequences

- Slice 4's runbook (`docs/runbooks/llamacpp-gpu.md` per ADR-0005) records the
  measured numbers and the final per-tier picks.
- Config gains per-tier model-id settings with the logical defaults; the adapter maps
  them to artifacts.

## Addendum (2026-06-29): Slice 4 measurements & model placement

First real bring-up on the 24 GB card, llama.cpp `server-cuda`,
16K context, single slot, all layers on GPU. VRAM is power-independent; load times below
were taken under a **55 W travel-power cap** (USB-C, not the 175 W brick) and are ~mount-read
bound, so they are *not* representative of full-power throughput.

| Cortex candidate | Weights only | + vision (mmproj) | Load (55 W) |
|---|---|---|---|
| Qwen3.5-9B Q4_K_M | 9.2 GB | 11.0 GB (mmproj F32, +1.8) | ~32-42 s |
| gemma-4-12B q4_0 | 11.0 GB | 11.3 GB (mmproj 0.18 GB, +0.3) | ~38-52 s |

1. **Cortex pick: gemma-4-12B** (`gemma-4-12b-it-qat-q4_0`). Both multimodal candidates
   land at ~11 GB, so VRAM does not decide it; gemma wins on being the stronger general
   chat model and on **QAT** (quantization-aware training, so its Q4 holds quality better
   than a post-hoc quant). Qwen's F32 projector is heavy but its 9B body is lighter;
   gemma's projector is tiny but its 12B body is heavier, so they converge at ~11 GB (16K).
2. **Context is a footgun.** llama-server defaults to the model's max context (262144) ×
   4 slots, pre-allocating ~8 GB of KV (17.3 GB total for Qwen-9B). The compose now sets
   `--ctx-size` (env `CORTEX_CTX_SIZE`, default 16384) and a single slot (the Model
   Manager serializes turns anyway).
3. **The GPU budget is a deliberate soft cap of 14 GB (env `CORTEX_VRAM_SOFT_CAP_GB`).**
   The user reserves the other ~10 GB of the 24 GB for a second monitor + gaming, so the
   AI stack stays under ~14 GB VRAM. The ~11.3 GB cortex therefore sits **comfortably under
   the cap** with ~2.7 GB of headroom. The cap was raised from 12 GB precisely to give the
   always-resident cortex room for KV/context/vision growth rather than sitting at the edge.
   Everything else still runs on **CPU** (or hybrid). The budget stays a single GPU-resident
   cortex; the CPU/hybrid split is a *requirement of the cap*, not an optimization. The cap
   is a single number the **Model Manager** enforces once it gains admission control (Slice
   7); until then it is documentation plus the levers that actually bound VRAM today, namely model
   choice, `CORTEX_CTX_SIZE`, and the per-`llama-server` `-ngl` (ADR-0005: engine flags are
   adapter/deployment, never core), exposed as env `CORTEX_NGL` (default 99); CPU-only
   (`-ngl 0`) and hybrid (partial `-ngl`, or `--no-kv-offload`) cost **zero core change**:
   - **Cortex** gets the full GPU; ~11.3 GB (16K ctx) sits under the 14 GB cap with ~2.7 GB
     headroom, so context size is still budget-bounded but no longer at the edge.
   - **Embedder** (nomic, 0.15-0.27 GB) runs on **CPU**; tiny + bursty (memory write/retrieval).
   - **Subagents** (2-4B) run on **CPU** (the GPU budget is spent on the cortex). Not one slot:
     the cortex spawns **one or more** subagents and picks their count and size within the
     budget (here CPU RAM + acceptable concurrency, not VRAM). The Model Manager admits or
     rejects each spawn against that budget (Slice 7).
   - **Brain** (~31B) is the swap model: it evicts the cortex, so it gets the full budget;
     hybrid `-ngl` / CPU-KV fallback if it doesn't fit (Slice 11).
   The Model Manager owns *allocation* against the soft cap; CPU models don't draw from it.
4. **Load ≈ mount-read bound** (~150-180 MB/s off the Windows drvfs bind mount) is the
   swap-latency bottleneck (ROADMAP assumption 2). A WSL-side/volume mirror of hot models
   is the lever if swap ever feels slow.
5. **Data dir reorganized** to `D:\Software\AI\Models` (and `…\AI\Database`). The earlier
   `AI Models` name (with a space) broke Docker Desktop's on-demand host-mount traversal
   from WSL; removing the space fixed it. Windows-native compose runs were unaffected.

## Addendum (2026-06-29): Slice 5 embedder pick + memory host validation

Both host halves of Slice 5 validated on the host machine (WSL + Docker Desktop). The
integration suites passed against real services:

- **`cortex_memory` vs. Postgres + pgvector 0.8.4.** The full `MemoryStore` contract
  (empty search, cosine ranking, top-k, roundtrip fidelity incl. the float4 embedding and
  the timestamptz instant) passed, proving the adapter's SQL (`docs/runbooks/memory-pgvector.md`).
- **`cortex_embedding` vs. nomic on a CPU `llama-server`.** A real embedding streamed back
  and was deterministic.

| Tier | Pick | Quant | Dim | Weights | Placement |
|---|---|---|---|---|---|
| **Embedder** | **nomic-embed-text-v1.5** | Q8_0 | 768 | 0.146 GB | **CPU** (`-ngl 0`), ~18 MiB RSS |

- **Embedder pick: nomic-embed-text-v1.5 Q8_0** is 768-dim, loads in ~1.2 s, negligible RAM,
  entirely off the GPU budget (as designed). It is the `docker-compose.memory.yml` default
  (`CORTEX_EMBED_MODEL_FILE`); `nomic-embed-text-v2-moe` (also 768-dim, larger) is the
  multilingual alternative, overridable via that env. Both are downloaded locally.
- **Schema is dimension-agnostic.** The `memories.embedding` column is an unbounded
  `vector`, so switching embedder/dimension needs no migration (an ANN index would; deferred).
