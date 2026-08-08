# ADR-0004: Model lineup (candidates locked)

- **Status:** Accepted (candidates locked 2026-06-29). Picks: cortex = **gemma-4-12B** (Slice 4),
  embedder = **nomic-embed-text-v1.5 Q8_0** (Slice 5), subagent = **gemma-4-E4B QAT q4_0**
  (Slice 7, revised to it on 2026-07-03), brain = **gemma-4-31B QAT q4_0** (Slice 11, measured
  2026-08-04); see the measurement addenda. Every tier is now picked.
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
vectors, not text, and are not prompt-injectable); the brain tier was opt-in and unrun until
**2026-08-04**, when the pick's row was measured (the last row below, and the
[ADR-0013](ADR-0013-untrusted-content.md) addendum of that date). The other three deep candidates
stay unmeasured.

| tier | candidate | framed obeyed / 10 |
|---|---|---|
| **cortex** | gemma-4-12B (pick) · Qwen3.5-9B | **0** · **0** |
| **subagent** | gemma-4-E4B | **0** |
| | Qwen3.5-0.8B | 0 (may be incompetence, not judgment) |
| | Qwen3.5-2B (pick) | 1 (output-laundering) |
| | Qwen3.5-4B | 2 |
| | gemma-4-E2B | 4 |
| **brain** (2026-08-04) | gemma-4-31B (pick), thinking on | **0** (the unframed control obeyed 1) |

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
  overflows every E4B spawn to CPU). **The VRAM half of that was a placeholder and is now
  measured: 3.5 GiB since 2026-08-08**, above the 3410 MiB the GPU-placed E4B tier peaks at with
  the floor bracketed, so one spawn fits the headroom and the next overflows
  ([ADR-0012](ADR-0012-resource-governance.md)'s measured-ask addendum). The memory and CPU asks
  in that bullet stand as measured.
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

**Both closed on 2026-08-04**, by the two addenda below, and by the agent rather than the user:
the premise that put them in that directory, a development card too small for a tier, was itself
measured false that day.

The measurement table above is **not** host work and never was: it was taken on that card on
2026-06-29, at 16K context and a single slot, with and without the mmproj. A briefly filed user
item asking for the with-projector figure again was withdrawn the same day it was filed
([ADR-0029](ADR-0029-vision-screen-capture.md)'s 2026-07-19 addendum).

No code changed here; this is a records correction at the origin ADR.

## Addendum (2026-08-04): the brain pick is gemma-4-31B, and the deciding axis is not VRAM

The deep tier is **gemma-4-31B-it-qat-q4_0**
(`google/gemma-4-31B-it-qat-q4_0-gguf/gemma-4-31B_q4_0-it.gguf`). This closes the one pick this
ADR left open, and with it the last `tbd` row of
[runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md).

All four candidates were run once each through the shipped path, meaning the `model-host`
sidecar's control API driven by hand with the cortex stopped first, so each candidate had the
card to itself exactly as a handoff leaves it. Only `CORTEX_MODEL_FILE_BRAIN` and
`CORTEX_CTX_SIZE_BRAIN` changed between runs; `CORTEX_NGL_BRAIN` stayed at 99, the context was
the shipped 8192, the slot count was one, and every artifact was read off the same read-only
models mount. VRAM is `nvidia-smi` total used, the table convention above; the card reports
24463 MiB and read 1867 to 1932 MiB with no model loaded across the whole session, so the
model's own cost is the third column. llama.cpp build `b10236-1464c62d8`, no power cap.

| Brain candidate | Artifact | Resident total | Model alone | Load to READY | Generation | Answered |
|---|---|---|---|---|---|---|
| **gemma-4-31B q4_0 (QAT), the pick** | 17.65 GB | **20996 MiB** | **19128 MiB** | **99.6 s** | ~31 tok/s | **4 of 4** |
| Qwen3.6-27B Q4_K_M (alternate) | 16.82 GB | 18319 MiB | 16443 MiB | 109.5 s | ~30 tok/s | 3 of 4 |
| Qwen3.6-35B-A3B UD-Q3_K_M | 16.60 GB | 17895 MiB | 15995 MiB | 117.3 s | ~80 tok/s | 1 of 4 |
| gemma-4-26B-A4B q4_0 (QAT) | 14.44 GB | 16474 MiB | 14607 MiB | 83.0 s | ~80 tok/s | 0 of 4 |

1. **Every candidate fits, so VRAM decided nothing.** Implication 4 predicted this ("Brain
   candidates (~15-18 GB) all fit alone in 24 GB") and it is the one prediction the run
   confirms outright. The spread is 14607 to 19128 MiB with the card to itself, and the
   largest candidate still leaves about 3.4 GB. **The hybrid `-ngl` / CPU-KV fallback that
   decision 3 recorded for this tier is therefore not needed and is not configured.** It stays
   on the shelf as the lever for a smaller card, which is what it was written for.
2. **What decided it is whether the model stops thinking.** Both families are reasoning models,
   and the last column is the number of escalation-grade questions (multi-step arithmetic under a
   deadline, a memory-fit puzzle, a two-sentence precision constraint, and a bug hunt in an async
   swap path) that produced an actual answer rather than an unfinished chain of thought, asked at
   a 4096-token budget. The two mixture-of-experts candidates are the fast ones, at roughly 2.6x
   the token rate of the dense pair, and they spend all of it: they reason correctly, arrive at
   the right derivation, and then either re-check it indefinitely or loop on a decimal expansion
   until the budget is gone. The answer is in the trace and never in the reply.
3. **That failure is not an artifact of the budget, and it reaches the deployment.** The brain
   sends no `max_tokens`, and the server's own default is `n_predict = -1` (read from `/props`),
   so the real bound on a turn is the context window. Re-asked with no cap at `--ctx-size 8192`,
   which is exactly how the tier ships, gemma-4-26B-A4B burned 8087 and 8057 tokens and returned
   `"content":""` on both questions, and Qwen3.6-35B-A3B burned 8092 and 8068 for the same empty
   result. **Both mixture-of-experts candidates consume the entire context and answer nothing.**
   Under the same uncapped condition gemma-4-31B answered in 4448 and 3847 tokens and
   Qwen3.6-27B in 3104 and 3340, both finishing on end-of-generation rather than on the wall.
   A candidate that cannot terminate is not a slow candidate; it is a turn that produces nothing,
   which is why the fastest two artifacts here are the two rejected ones.
4. **Between the two dense candidates the margin is real but narrow.** Both answered everything
   asked of them uncapped, and every completed answer was correct on the checkable questions.
   The one question with no key, which asked which of a soft cap and a hard limit needs admission
   control to mean anything, drew "the hard limit" from the pick on both of its runs and from
   every other candidate that answered it, except Qwen3.6-27B, which said "the soft cap" once and
   "the hard limit" once. This repo's own position is the soft cap, since that is the number
   decision 3 says the Model Manager will enforce, so the tier does not reach the house answer
   unprompted. Worth knowing before a brain phase is asked to reason about the budget it is
   running inside.
   gemma-4-31B wins on being **QAT**, which is the same reason decision 1 gave for the cortex,
   on reaching its answers in fewer tokens (4 of 4 inside a 4096 budget against 3 of 4), and on
   being the same family as the shipped cortex, so one chat template and one prompt idiom span
   both tiers. Qwen3.6-27B Q4_K_M loses on those and wins on 2.7 GB of VRAM, so it is recorded
   as **the documented alternate** for a deployment that wants more of the card left over during
   a handoff, and it is one `CORTEX_MODEL_FILE_BRAIN` away.
5. **Context has room to grow.** At `CORTEX_CTX_SIZE_BRAIN=16384` the pick read 21667 MiB
   resident, 19786 MiB over the floor, which is 658 MiB for the second 8K of KV. The shipped
   8192 default is therefore not a fit constraint, and doubling it costs well under a gigabyte.
6. **Load stays mount-read bound, as decision 4 said.** The four cold loads run 142 to 177 MB/s
   off the mount (17.65 GB in 99.6 s for the pick), squarely inside the 150 to 180 MB/s this ADR
   already recorded, so nothing here argues for the WSL-side mirror lever. A bare load of the
   pick is **99.6 s**, which is the figure the swap's load phase is compared against and leaves
   the shipped `CORTEX_SWAP_LOAD_TIMEOUT_S` default of 300 s about two thirds unspent. A second
   load of the same artifact took 66.4 s with the file partly in page cache, so treat 99.6 s as
   the cold number and the timeout margin as the cold-case margin.
7. **The eviction half is unchanged at tier scale.** Stopping an idle deep tier answered in
   0.92 s and VRAM fell to 1874 MiB; restarting the cortex answered in 0.12 s and reached READY
   35.7 s later at 9691 MiB. Both container health checks stayed green throughout, the sidecar's
   because it asks for either tier and the brain's because it asks only that `Health` answered.
8. **One incidental observation, recorded rather than acted on.** With this llama.cpp build the
   cortex tier read about 9.7 GB `nvidia-smi` total at 16K text-only, against the 11.0 GB this
   ADR measured for it in 2026-06-29's build. That is a different build and a text-only start,
   not a controlled re-measurement, so **no cortex row is changed here**; it is written down
   because the swap arithmetic depends on the cortex figure and a future sitting should confirm
   which number the deployment actually pays.

The header's pick line also carried a stale subagent entry, naming Qwen3.5-2B where the
2026-07-03 addendum below had already revised the pick to gemma-4-E4B. It is corrected in the
same pass, for the reason [runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md) gives for its
own version of that slip:
[ADR-0017](ADR-0017-subagent-model-safety.md) binds the untrusted-content safety default to the
current subagent pick by its logical id, so a header naming the wrong model names the wrong
safety default.

**Closed later the same day: the injection-harness row for the brain**, which the injection addendum
above had recorded as opt-in and unrun since 2026-07-01. The pick answers **0/10 framed** against an
unframed control that obeyed 1, so the deepest tier is as injection-robust as the cortex, and the
one attack the control fell to is the tool exfil, where an unframed model emitted a real
`send_email` call and the shipped framing stopped it. That row is now in the table above, and the
evidence, the checks that make a perfect score believable, and what it does and does not imply for
the tainted-escalation stance are in
[ADR-0013](ADR-0013-untrusted-content.md)'s 2026-08-04 addendum. The three candidates this addendum
rejected were not probed: an alternate adopted later buys its own harness row.

## Addendum (2026-08-07): the cortex row, re-measured as note 8 asked

The swap-latency addendum's note 8 recorded that the cortex tier read about 9.7 GB of `nvidia-smi`
total at 16K text-only against the 11.0 GB this ADR measured on 2026-06-29, declined to change any
row on the strength of it, and asked a later sitting to confirm which number the deployment pays.
It was right to wait and right to ask: the answer moved a shipped default.

Measured on the 24463 MiB card, through the model-host sidecar, at the tier's shipped shape
(`-ngl 99 --ctx-size 16384 --parallel 1 --jinja` with the projector and `--image-max-tokens 1024`),
the cortex costs **8400 to 8484 MiB idle and 8573 MiB at its peak**, both above a floor read with
the tier stopped immediately before the load and again after the last arm (1261 to 1301, then 1259
to 1308 MiB). Read the way this ADR's table reads, as total used with the model resident, the same
peak is **9832 MiB**, so note 8's incidental 9.7 GB was very nearly right and the 11.0 and 11.3 GB
rows above are a different llama.cpp build's numbers.

**The rows above are left as they were measured**, because they are a dated comparison between four
candidates on one build and rewriting one cell would make the table a mixture of two sessions. What
they must not continue to do is set a live default, and that is the part this addendum changes:
`CORTEX_VRAM_CORTEX_GB` is 8.6 from today, argued with the full table of readings at
[ADR-0012](ADR-0012-resource-governance.md)'s re-measured-reservation addendum, which owns the
placer's budget. The pick itself is untouched, gemma-4-12B being chosen on chat quality rather than
on VRAM, and so is the 14 GB soft cap, which is the user's policy about the card rather than a
measurement of anything.

One correction the rows do carry, stated here so no later reader repeats the arithmetic: this ADR's
figures are `nvidia-smi` total used, so they include whatever the Windows desktop held at the time.
That is a fine convention for comparing candidates against each other on one afternoon, and a wrong
one for a budget term that is subtracted from a cap alongside a per-model ask. Decision 3's
"~11.3 GB cortex ... ~2.7 GB headroom" reads a floor into the reservation and then spends the rest
as headroom; the headroom is really 5.4 GiB.
