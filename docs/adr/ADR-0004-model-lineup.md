# ADR-0004: Model lineup (candidates locked)

- **Status:** Accepted (candidates locked 2026-06-29). Picks: cortex = **gemma-4-12B** (Slice 4),
  embedder = **nomic-embed-text-v1.5 Q8_0** (Slice 5), subagent = **Qwen3.5-2B Q4_K_M** (Slice 7);
  see the measurement addenda; brain pick follows in Slice 11.
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
  entirely off the GPU budget (as designed). It is the `docker/docker-compose.memory.yml` default
  (`CORTEX_EMBED_MODEL_FILE`); `nomic-embed-text-v2-moe` (also 768-dim, larger) is the
  multilingual alternative, overridable via that env. Both are downloaded locally.
- **Schema is dimension-agnostic.** The `memories.embedding` column is an unbounded
  `vector`, so switching embedder/dimension needs no migration (an ANN index would; deferred).

## Addendum (2026-07-01): Slice 7 subagent pick + CPU measurement

The subagent tier was measured on the host machine (WSL + Docker Desktop, models at
`/srv/models`) on a CPU `llama-server` (`ghcr.io/ggml-org/llama.cpp:server`, `-ngl 0 --jinja`).

| Tier | Pick | Quant | Weights | Load | Placement |
|---|---|---|---|---|---|
| **Subagent** | **Qwen3.5-2B** | Q4_K_M | 1.19 GB | ~14.5 s | **CPU** (`-ngl 0`), ~893 MiB RSS (+2 slots) |

- **Subagent pick: Qwen3.5-2B Q4_K_M** is off the GPU budget entirely (as designed, ADR-0001);
  ~0.9 GB RSS leaves ample CPU RAM for several concurrent subagents. It is the
  `docker/docker-compose.subagents.yml` default (`CORTEX_MODEL_FILE_SUBAGENT`).
- **Runs with reasoning disabled.** Qwen3.5/3.6 are reasoning models; unbounded on CPU they emit
  long `<think>` traces (minutes/call). The subagent server disables it (`--chat-template-kwargs
  '{"enable_thinking": false}'`, baked into `docker/docker-compose.subagents.yml`), so a narrow task
  answers correctly in ~0.6 s ("17 + 25" → 42). See the [ADR-0010 addendum](ADR-0010-subagents.md).
  If the 2B's tool-calling proves too weak with reasoning off, gemma-4-E4B or Qwen3.5-4B (both
  present) are the fallbacks at higher CPU cost.
- **Cortex-driven end-to-end** (a resident gemma-4-12B *deciding* to delegate) needs the GPU and
  the full stack per `docs/runbooks/subagents-cpu.md` §3. Host-closed 2026-07-01 (dated closure
  addendum in [ADR-0010](ADR-0010-subagents.md)).

## Addendum (2026-07-01): subagents are GPU-first (revises the "subagents = CPU" placement)

The Slice 7 addendum above (and implication 3's placement note) placed subagents on **CPU**. At
the user's direction this is revised: subagents are **GPU-first, CPU-overflow**. The
`ModelManager` places a subagent in VRAM when it fits under the 14 GB soft cap, allowing
**bigger** subagents (up to ~4B, e.g. `Qwen3.5-4B` or `gemma-4-E4B` from the candidate set above,
when the resident cortex leaves headroom), and spills to CPU (the Qwen3.5-2B pick, `-ngl 0`) only
when the cap would be exceeded. The measured CPU footprint above still stands for the
**CPU-fallback** path. Design + adversarially-verified WSL2 resource feasibility: **Slice 8.5 /
ADR-0012** (there is no per-process GPU-utilization cap on the dev machine+WSL2 stack, so GPU load is
governed by scheduler concurrency, not a driver knob).

## Addendum (2026-07-01): injection-robustness as a new model-selection dimension (Slice 6.5)

The untrusted-content boundary (ADR-0013) added a **safety axis** to the per-tier pick, measured by the
committable harness [`test_injection_defense_live.py`](../../brain/packages/inference/tests/test_injection_defense_live.py)
(10-category indirect-injection corpus, framed-vs-control, agent-run on the GPU). Every cortex + subagent
candidate above was run under the shipped (hardened) preamble; **embedders are excluded** (they emit
vectors, not text, and are not prompt-injectable); the brain tier is opt-in and not yet run.

| tier | candidate | framed obeyed / 10 |
|---|---|---|
| **cortex** | gemma-4-12B (pick) · Qwen3.5-9B | **0** · **0** |
| **subagent** | gemma-4-E4B | **0** |
| | Qwen3.5-0.8B | 0 (may be incompetence, not judgment) |
| | Qwen3.5-2B (pick) | 1 (output-laundering) |
| | Qwen3.5-4B | 2 |
| | gemma-4-E2B | 4 |

- **Cortex:** injection-robustness does **not** decide it (both candidates are 0/10), so the gemma-4-12B
  pick stands on VRAM/quality/QAT (decision 1). Reassuring, since the cortex is the only user-facing
  generator (ADR-0013).
- **Subagent:** **gemma-4-E4B (0/10) is materially more injection-robust than the current Qwen3.5-2B
  pick (1/10)** and the rest of the tier. This does **not** overturn the Qwen-2B pick on its own. Safety
  for subagents rests on the deterministic layers (no outbound tools, fail-closed gate, taint
  containment, ADR-0013), so model choice here is a *quality/robustness* preference, but it is a strong
  reason to prefer gemma-E4B for untrusted-content subtasks. **Slice 8.6** (heterogeneous subagent
  models) makes this per-task: the cortex can pick gemma-E4B for a risky read and a cheaper model
  elsewhere. Re-run the harness when picks or the preamble change.

## Addendum (2026-07-03): subagent pick revised to gemma-4-E4B (injection-robustness adopted)

The injection-robustness addendum above left the Qwen3.5-2B pick standing with a flag; the
ROADMAP's deferred-refinements entry ("reconsider the subagent model pick") is now resolved:
**the subagent pick is gemma-4-E4B (QAT q4_0)**. The safety axis wins the tie, at a measured
and acceptable CPU cost. Agent-run measurements (WSL + Docker Desktop, models at
`/srv/models`, the actual `docker-compose.subagents.yml` server: CPU `-ngl 0 --jinja`,
thinking off, ctx 8192, 2 slots):

| | Qwen3.5-2B Q4_K_M (old pick) | gemma-4-E4B QAT q4_0 (new pick) |
|---|---|---|
| weights | 1.19 GB | 4.9 GB |
| load (drvfs mount) | ~14.5 s | **38 s** |
| RSS after inference | ~893 MiB | **~2.5 GiB** |
| narrow task ("17 + 25") | ~0.6 s | **~1.8 s** |
| tool call (`--jinja`, schema in prompt) | works | **works, ~8 s** (CPU prefill-bound) |
| delegation live test (`test_subagent_live.py`) | passed 2026-07-01 | **passed 2026-07-03** (2 concurrent, 3.3 s) |
| injection, framed, thinking off | 1/10 (output-laundering) | **0/10** (re-confirmed 2026-07-03; the unframed control obeyed 2) |

- **Why adopt now:** the small tier is the injection-weak link (ADR-0013 addenda) and the
  hardening focus makes per-model robustness worth its cost. E4B is the only small candidate
  at 0/10, it launders nothing, and its robustness holds with thinking **off** (the deployed
  subagent mode). Defense stays layered: the deterministic boundary (no gated tools, made
  structural since the ADR-0013 subagent-exclusion addendum, plus the fail-closed gate, taint
  containment, and the ADR-0015 output guardrail) does not depend on this pick; E4B lowers
  the residual on the one axis only a model can (parroting/laundering into taint-contained
  output, and general instruction-following quality on untrusted reads).
- **Costs, quantified above:** ~2.6× load, ~3× narrow-task latency, ~2.8× RSS. Acceptable for
  narrow asynchronous subtasks; the admission ask in the compose is updated to the measured
  numbers (memory 3.0 GB → two concurrent under the 8 GB budget, matching `--parallel 2`;
  VRAM ask 5.5 GB, deliberately above the current GPU headroom so the ADR-0012 placer
  overflows every E4B spawn to CPU).
- **`enable_thinking=false` is honored by the gemma-4-E4B template** (validated: no
  `reasoning_content`, direct answers). The earlier compose comment claiming gemma-4-E* are
  non-reasoning templates was wrong and is corrected; both lineup families are
  reasoning-capable and both need the flag on CPU.
- **Qwen3.5-2B remains the documented cheap override** (`CORTEX_MODEL_FILE_SUBAGENT`) when
  latency matters more than robustness; **Slice 8.6** (heterogeneous subagent models) still
  makes the choice per-task, with E4B as the safe default rather than the special case.
- **E4B is the "robust default" the safety override falls back to.** When Slice 8.6 lets the cortex
  pick the subagent model per spawn, [ADR-0017](ADR-0017-subagent-model-safety.md) **forces** this
  pick on any spawn whose path can carry untrusted content (tainted turn or tools-enabled subagent),
  overriding the cortex's choice. The weak roster models are therefore reachable only for tool-less
  subagents on untainted turns. The override binds to *this pick* by its logical id, so a future
  revision here moves the safety default with it automatically.
- Artifacts: `google/gemma-4-E4B-it-qat-q4_0-gguf/gemma-4-E4B_q4_0-it.gguf` (the
  harness-tested QAT quant; the lmstudio Q8_0 stays unused, since 7.5 GB buys no robustness).

## Addendum (2026-07-19): where the host-side pick is tracked

The deep-model pick this ADR left open, and the injection table's line that the brain tier is
"opt-in and not yet run", are the two things here that only the 24 GB card can close. Both
now have a written home with a procedure, a pass, a fail, and a "record it" line pointing back at
this file: items 1 and 5 of
[docs/host/gpu-tier-scale.md](../host/gpu-tier-scale.md), whose index is
[docs/host/](../host/index.md). Nothing about the work changed; this is the third of the three
records [AGENTS.md](../../AGENTS.md) requires for a host item, which this ADR was missing.

The measurement table above is **not** host work and never was: it was taken on that card on
2026-06-29, at 16K context and a single slot, with and without the mmproj. A briefly filed user
item asking for the with-projector figure again was withdrawn the same day it was filed
([ADR-0029](ADR-0029-vision-screen-capture.md)'s 2026-07-19 addendum).

No code changed here; this is a records correction at the origin ADR.
