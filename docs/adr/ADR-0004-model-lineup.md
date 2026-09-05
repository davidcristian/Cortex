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
2. **The default context size is a hazard.** llama-server defaults to the model's max context (262144) ×
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
  **Corrected 2026-08-26 (ADR-0005 thinking-lever addendum).** The first sentence is wrong and the
  validation behind it does not support it: the prompts it was read on invite no deliberation, so a
  direct answer with no `reasoning_content` is what this pick does with the kwarg, without it, and
  with it set to true. On a prompt that does invite deliberation, which a `response_format`
  reliably makes of an ordinary summarization, the E4B pick writes a full trace with the kwarg set
  at the server, at the request, and at both. What the second and third sentences say still stands,
  and is now stronger: both families are reasoning-capable, and the flag they need on CPU is a pair,
  `--reasoning-budget 0` beside the kwarg.
  **The first sentence is restored 2026-08-27 (ADR-0005 switch-is-advisory addendum), with the
  shape named.** The correction above threw out the right claim with the bad validation. Measured on
  a prompt that does invite deliberation, on a server carrying neither reasoning flag, the E4B
  template honours the kwarg on a **plain** request (654 characters of trace without it, none with
  it) and the same key does nothing at all once the request carries a `response_format` (599
  without, 664 with). So the correction's own example, an ordinary summarization made deliberative
  by a `response_format`, is the one shape the kwarg never reaches on this pick, which is why it
  read as a template that ignores the flag. The pair the tier ships is unchanged and is what
  covers both shapes.
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
[docs/host/index.md#gpu-tier-scale](../host/index.md#gpu-tier-scale), whose index is
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
   decision 3 recorded for this tier is therefore not needed and is not configured.** It remains
   available as the lever for a smaller card, which is what it was written for.
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
   A candidate that cannot terminate produces no turn output at all, whatever its token rate,
   which is why the fastest two artifacts here are the two rejected ones.
4. **Between the two dense candidates the margin is real but narrow.** Both answered everything
   asked of them uncapped, and every completed answer was correct on the checkable questions.
   The one question with no key, which asked which of a soft cap and a hard limit needs admission
   control to mean anything, drew "the hard limit" from the pick on both of its runs and from
   every other candidate that answered it, except Qwen3.6-27B, which said "the soft cap" once and
   "the hard limit" once. This repo's own position is the soft cap, since that is the number
   decision 3 says the Model Manager will enforce, so the tier does not reach this repo's answer
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

## Addendum (2026-08-11): the ANN index measured, and why the schema stays dimension-agnostic

Decision 4's schema note above says the `memories.embedding` column is an unbounded `vector` so
switching embedder or dimension needs no migration, and adds in parentheses that an ANN index
would. That parenthesis was the whole of the argument for deferring the index, and the deferred
entry it produced (`docs/refinements/index.md#memory`) carried a second claim beside it, written into
`docker/postgres/init.sql` and `docs/modules/brain-memory.md` alike: that an exact cosine scan is
"fine at personal scale". Both halves were measured today against real pgvector 0.8.4 on
PostgreSQL 16.14, the shipped `pgvector/pgvector:pg16` image from
`docker/docker-compose.memory.yml`, in a scratch database of its own so no real memory was read or
written. **One half held and the other did not.**

**Method.** A synthetic corpus of 768-column unit vectors, the width of the shipped
nomic-embed-text-v1.5 pick, drawn from 256 topic centres inside one shared cone, populated by
`COPY` into the schema `init.sql` really creates and queried through
`PgVectorMemoryStore.search` itself rather than through hand-written SQL, so the numbers include
the literal rendering and row parsing a turn actually pays. The requested width is 20, which is
what ships: `DEFAULT_RECALL_K` is 5 and the judge's `recall_pool_factor` is 4, and the default
`GlobalMemoryScope.read_scopes` returns `None`, so the statement under test is `_SEARCH_ALL` with
`LIMIT 20` and no scope filter. The geometry was checked against the real embedder rather than
assumed: 20 sentences through the live CPU `llama-embed` sidecar give a mean pairwise cosine of
0.381 with a standard deviation of 0.054, against 0.170 and 0.043 for the synthetic corpus, so the
synthetic spread is comparable and its cone is looser.

**The scan is not free, and it is not a few milliseconds.** At 1,000 rows the search takes 19 ms,
and `EXPLAIN (ANALYZE, BUFFERS)` attributes 18.2 of its 18.7 ms of server time to the sequential
scan at 9,088 buffer hits, about nine per row, because pgvector gives `vector` an `attstorage` of
`e`: every embedding lives out of line in TOAST and every candidate row is detoasted before its
distance can be taken. The heap is 512 kB where the table totals 4,688 kB. At 220,000 rows the
same search takes **1,478 ms at the median** (n=8, 1,458 to 1,521), which is not a few milliseconds
against the 0.515 s of time to first token the turn-cost addendum measured for a recalling turn.
It is roughly three times the whole of it.

| Rows | `search` k=20, unfiltered (ships) | k=5 (`raw`) | scoped to one session |
|---|---|---|---|
| 1,000 | 21.2 ms median (18.9 to 25.8) | 20.0 ms (18.3 to 21.2) | 1.3 ms (1.1 to 1.7) |
| 220,000 | 1,478 ms median (1,458 to 1,521) | 1,479 ms (1,440 to 1,502) | not re-measured |

The requested width barely moves it, k=5 and k=20 costing the same, which is the signature of a
cost that is per candidate rather than per returned row. The scope filter is the one thing that
does move it: a session holding about 40 rows answers in 1.3 ms at the same table size, so a
deployment running `CORTEX_MEMORY_SCOPE=session` never had this problem, and the default global
space is where it lives.

**The index is fast and its recall is not free.** An `hnsw` index over
`vector_cosine_ops` at the defaults, `m=16` and `ef_construction=64`, took 184 s to build at
220,000 rows and occupies 859 MB, more than the 688 MB table it indexes. With `hnsw.ef_search=40`
the same search answers in **5.5 ms at the median** (3.0 to 8.1), a factor of 268. Set against the
exact answer it replaces, its **mean overlap is 0.550 at k=20 and 0.575 at k=5, and the worst
single query kept none of the twenty the exact scan returned**. An `ivfflat` build did not
complete: at `lists=316` it needs 69 MB of `maintenance_work_mem` against the 64 MB default, which
is an operational fact worth recording since nothing in the compose raises it.

**A third option was measured and does not rescue the scan.** Since the cost is detoasting,
`ALTER COLUMN embedding SET STORAGE PLAIN` plus a `VACUUM FULL` should have bought most of it back
for no approximation at all. It buys 22%: 1,154 ms at the median against 1,478 ms, while the table
grows from 688 MB to 924 MB, because a 3,080-byte vector stored inline fits two rows to an 8 kB
page and wastes the rest. The arithmetic, not the detoasting, is the remaining four fifths.

**Decision: the schema stays dimension-agnostic and no ANN index ships today.** The parenthesis
above is upheld, and it is upheld more strongly than when it was written, because the migration it
warns about is now specified rather than gestured at. `hnsw` and `ivfflat` both require a typmod,
so the column must become `vector(768)`; the `ALTER` itself is cheap at 3.5 s, but what it costs is
the property decision 4 exists to state. After it, an embedder of another width cannot be adopted
by changing `CORTEX_EMBED_MODEL_FILE`, which is exactly how this repo ships the alternative
(`nomic-embed-text-v2-moe`, also 768, and every model that is not): the insert fails outright on a
dimension mismatch, which is the good case, and the bad case is a redeployment that rebuilds the
column at the new width and leaves an index built for the old one, which pgvector will not do
silently but which a hand-run migration can. **An index that must be rebuilt whenever the embedder
changes is a deployment step rather than a schema property**, and this repo has no migration runner
to own it.

That would still be worth paying if the index were free of recall cost, and it is not. What the
measurement cannot yet say is how much of the 0.550 overlap is a defect and how much is an artifact
of the corpus: 256 centres across 220,000 rows puts about 860 near-tied members around each query,
so the exact top 20 and the approximate top 20 are drawing from a pool whose distances differ in
the fourth decimal, and a set-overlap metric punishes that severely while a reader would not notice
it. **Set overlap is the wrong measurement and it is the one that was run.** The right one is the
score delta, how much worse in cosine terms the approximate answer is than the exact one, and it is
not measured here. Until it is, the honest reading of "the worst query kept 0 of 20" is that it is
unexplained rather than that it is harmless, and an unexplained recall loss is not something to
ship underneath a personal assistant's memory to save a second.

**What this changes for the deferred entry.** It does not close it, and it removes its stated
reason. The entry, `init.sql`, and the memory module doc all justify the deferral with a claim that
exact search is fine at personal scale; that claim is true through roughly ten thousand memories,
where the scan costs about 70 ms, and false by a hundred thousand. At one memory per turn, which is
what the v1 write policy records, ten thousand memories is a few months of daily use and two
hundred thousand is several years of it. So the entry is **re-triggered on measurement rather than
struck**: its trigger is no longer "when recall feels slow", which was never going to fire before
the store was already too big, but the score-delta calibration named above, and the comments that
call the scan fine at personal scale are corrected to say through what scale.

## Addendum (2026-08-16): the MTP deferral priced, and neither half of its sentence still blocks it

Prices the two-line MTP deferral under the candidate table, which reads "deferred because they use
more memory; revisit only if latency demands it". It stays open, no code changes, and the finding
is that both clauses have been overtaken by measurement while the thing that actually blocks the
work was never named.

**The memory clause is survivable on the tier that would want this.** Measured on 2026-08-07, the
deep model alone reads 20671 to 20723 MiB and takes a 2878 MiB peer beside it at 23555 to 23642
MiB with about 908 MiB free, its decode unharmed at 28.92 to 29.82 tok/s against 25.07 to 33.28
alone. A companion artifact of that size is affordable there. It is unaffordable exactly where the
lineup already says so, the cortex beside the deep model, which needs 29139 MiB against 24463 and
pays for the overcommit in decode rather than in an error.

**The latency clause has arguably already fired.** The pick reaches an answer on hard questions in
roughly 3800 to 4500 tokens at about 31 tok/s, so a deep turn spends something near two minutes
generating on top of a 99.6 s load. Decode is the larger half of what a user waits for on that
tier, which is the condition the sentence set, so "revisit only if latency demands it" no longer
names anything that has not happened.

**What blocks it is that nothing in this tree can name such an artifact or hand it to a server.**
The repo holds no draft or speculative decoding flag under any name and no MTP filename.
`llama_server_argv` builds a fixed flag tuple plus a per-tier `extra` whose only producers are the
thinking-off pair and the vision tail, there is no env hook for a free-form argument, and the
roster is fixed at boot on purpose, since a request-supplied argv would be remote code execution
against the GPU container ([ADR-0030](ADR-0030-brain-handoff.md)'s model-host seam). Reaching it is
a typed field on `TierArgs`, a second artifact path per tier and a VRAM budget row, none of which
is worth writing before an artifact exists that the pinned server accepts. The entry's trigger is
therefore upstream-shaped and now says so: an MTP or draft artifact for a shipped tier that this
build of llama.cpp loads at all.

## Addendum (2026-08-28): every chat entry answers the thinking switch, and the answer is its template's

Earlier addenda measured this lineup on VRAM, load time, decode rate, injection robustness and
answer quality. None of them measured it on the thinking switch, the field a caller sends to ask
for a short answer rather than a long one. `GenerationBounds(thinking=False)` renders as
`chat_template_kwargs: {"enable_thinking": false}`, and whether a pick then skips its deliberation
had been measured on two entries, both gemma-4
([ADR-0005](ADR-0005-llamacpp-engine.md)'s switch-is-advisory addendum). Every remaining chat entry
has now been asked, five draws a cell, each server carrying **neither** reasoning flag; the
per-entry table with the placements, the chat formats and the engine digests is that addendum's
lineup section. Three readings belong here, where picks are chosen.

1. **Every entry honours it on a plain request**, 0 draws of 5 deliberating with the switch sent
   against 5 of 5 without it. So the shipped bounds that pair a cap with the switch and carry no
   schema are safe on anything a deployment names off this table, and no pick revision is owed to
   this reading.
2. **Under a `response_format` the lineup splits, and it splits inside a family.** The dense gemma-4
   entries hold, the 12B, the 31B and the 26B-A4B alike; both gemma-4-E entries deliberate straight
   through the switch, the E2B on 5 draws of 5 and the E4B on 4. Every Qwen entry holds on both
   shapes, which puts the claim [ADR-0010](ADR-0010-subagents.md) and the subagent compose file
   carried on real footing at last: it was read off a `17 + 25` that invites no deliberation and
   therefore proved nothing either way, and re-asked on a prompt that does invite one, it is true.
3. **The deciding property is the entry's own chat template, and it is readable before a pick is
   made.** Ask a candidate's server for its rendered prompt with the kwarg and without it: an entry
   whose template renders a thought block already opened and closed holds under a schema, and one
   whose template drops the block and adds nothing in its place does not. That held
   on every entry measured. It is the cheapest selection input in this ADR, one HTTP call against a
   loaded server, and it is the one to take on a candidate that will serve a side call carrying a
   schema.

4. **That column now costs answers, and it decides what a subagent override buys**
   ([ADR-0028](ADR-0028-grammar-constrained-subagents.md)'s lineup addendum, 2026-08-28). Three
   entries of the subagent row have been run through the constrained reply path at 288 runs each, and
   the split above predicts the rate at which each writes its answer into the reasoning channel a
   delegated run drops: Qwen3.5-2B, on the holding side, does it on 0 draws of 288; gemma-4-E4B on 8
   of 96 constrained draws and the E2B on 14. The consequence for a chooser is that the sentence the
   constrained path appends to every subtask, which recovers the E4B's narrating shape from 9 of 32
   to 29 of 32, leaves gemma-4-E2B **worse overall than without it**, 84 of 96 against 90. The
   shipped default and the shipped roster alternate are both on the paying side; an operator who
   overrides `CORTEX_MODEL_FILE_SUBAGENT` to the E2B is the one this reading is for, and the
   subagent runbook says so where the override is documented.

5. **The subagent row is now measured whole, and its five entries spread widely**
   ([ADR-0028](ADR-0028-grammar-constrained-subagents.md)'s row addendum, 2026-08-28). All five
   entries have been through the constrained reply path at 288 runs each, 1440 in all. The residue
   column above survives the other two: Qwen3.5-0.8B and Qwen3.5-4B write into the reasoning channel
   on **0 draws of 288 each**, which takes the family to 0 of 864 and the column to five predictions
   out of five. What the column does not touch is the answer rate, and that is where this row
   spreads: under the shipped path the five entries deliver between **66 and 94 of 96** on identical
   work. The floor is the smallest entry, Qwen3.5-0.8B, which answers an extraction on 12 draws of
   32; the ceiling is Qwen3.5-4B, whose bare envelope costs it nothing measurable against its own
   unconstrained arm (91 of 96 against 92). So size within a family tracks the cost and size across
   families does not, and the appended sentence is a gain on three entries of the five and a cost on
   two, with only the default pick's gain large. Both entries a deployment ships stay on the paying
   side. The
   selection reading for a chooser is that this row is a spread and not a tier, and the runbook
   names the two entries to override to last.

**What this does not change.** No pick moves. The subagent tier's two reasoning-off flags stay
exactly as they are: `--reasoning-budget 0` covers the gemma-4-E entries on the shape their template
does not, it costs nothing on an entry whose template already holds, and a tier carrying both flags
suppresses reasoning for either entry without depending on which one it was given.

## Addendum (2026-08-30): the embedder's override variable is renamed into the artifact family

The embedder pick above and decision 4 are unchanged. What changed is the name of the variable
that overrides it: `CORTEX_EMBED_MODEL_FILE` is now **`CORTEX_MODEL_FILE_EMBED`**, so the CPU
embedder's GGUF is named the way every other model artifact in this tree is, and the gate that
holds that convention (`scripts/flagcheck.py`) covers this variable too rather than exempting it
for serving no chat. The reasoning, the alternative that was refused, and the size of the rename's
own risk are in
[ADR-0029](ADR-0029-vision-screen-capture.md)'s addendum on a non-chat artifact naming itself in
the family; the operator-facing half is in
[docs/runbooks/memory-pgvector.md](../runbooks/memory-pgvector.md).

The old name is read by nothing now, so a host whose `.env` still sets it runs the shipped
nomic pick rather than the override, which matters only to a deployment that had named the
`nomic-embed-text-v2-moe` alternative this ADR ships. The sentences above and every measurement
below them keep their own wording, this addendum being their correction, which is how a superseded
name is handled here.

## Addendum (2026-09-04): the injection harness takes the tier's argv, and the subagent rows run both ways

Every subagent row in the injection table above, the E4B pick's **0 of 10** among them, was
measured with the thinking switch in a place no deployment puts it.
[`test_injection_defense_live.py`](../../brain/packages/inference/tests/test_injection_defense_live.py)
started its server with `-ngl 99 --ctx-size 8192 --parallel 1 --jinja` and no reasoning flag, and
sent `chat_template_kwargs: {"enable_thinking": false}` on every request of a thinking-off row. The
stack does the opposite. Every subagent server this repo starts carries
`--chat-template-kwargs '{"enable_thinking": false}'` and `--reasoning-budget 0` on its command
line, which `scripts/flagcheck.py` requires of both placements, and a `PlacedAttempt` sends no
request key at all. On a plain request the two render the same prompt, but they are separate
levers ([ADR-0005](ADR-0005-llamacpp-engine.md)'s thinking-lever and marker addenda), and a build
on which they parted ways would have moved this harness's number without moving the tier's.

**The harness can be handed a tier's flags now.** A `Switch` says where one row's reasoning-off
answer comes from: `argv`, which `server_argv` appends to the command line, and `request_key`,
which `completion_body` puts in the request. `SWITCHES` holds the two a thinking-off row picks
between, `request-key` and `shipped-argv`, and the text arm runs once per entry. A tier that
deliberates on purpose pulls neither lever, so the cortex and deep rows skip their second copy
rather than measuring the same cell twice. `-k shipped-argv` selects the rows drawn as the stack
sends them, and `-k request-key` the replicates of every subagent number published before this
date.

**Neither spelling is typed into the harness.** `shipped_reasoning_off()` builds `ModelHostConfig`
and takes its subagent tier's own `extra`, and `template_kwargs()` decodes the JSON that tier's
flag carries into the request key, so the two routes are one answer read twice rather than two
copies of one. That is why this change adds no `crosscheck` entry where the shipped image budget
needed one: there is no second declaration to hold equal. What stands in its place is a reading
that fails closed. A tier that renamed a flag, dropped half the pair, or changed what it tells its
template fails `test_switch_rows.py`, which is where the harness's claims about the sidecar and
about its own two rows are written down, and which CI runs.

**Measured 2026-09-04** on `ghcr.io/ggml-org/llama.cpp:server-cuda` build **10680** (`d7bd3bfca`),
the build the hand run behind
[R-525](../refinements/tasks/525-the-injection-harness-sends-a-request-key-and-never-the-tiers-argv.md)
used, at `-ngl 99` on the 24 GB card. Ten attacks per row, a framed arm and an unframed control in
each. Sittings were spent where a lever could show: four on the pick, whose published number is the
one this ADR rests on, three on E2B, the small candidate the table above records obeying the most,
and four on Qwen3.5-4B once its first pair of matrices disagreed. The two candidates whose rows
reproduced their published counts on the first pair were left at one sitting each.

| candidate | sittings | `shipped-argv` framed / 10 | `request-key` framed / 10 | unframed control / 10 |
|---|---|---|---|---|
| **gemma-4-E4B (subagent pick)** | 4 | **0** every sitting | **0** every sitting | 2 every sitting |
| gemma-4-E2B | 3 | 3 every sitting | 3 every sitting | 3 every sitting |
| Qwen3.5-0.8B | 1 | 0 | 0 | 0 |
| Qwen3.5-2B | 1 | 1 | 1 | 2 |
| Qwen3.5-4B | 4 | 2, 2, 3, 2 | 3, 2, 2, 2 | 3 to 4 |

**The flags reach the engine, checked rather than assumed.** A `shipped-argv` server logs
llama.cpp's own `Setting 'enable_thinking' via --chat-template-kwargs is deprecated` on startup and
a `request-key` server logs nothing of the kind, which is the engine confirming which lever the row
pulled before any completion is scored.

**The reading: on this lineup the two routes draw the same matrix.** On both gemma candidates every
cell was identical between the switches and identical across sittings, the attack names behind the
counts included, and the pick's row is 0 of 10 in all four sittings on both. Qwen3.5-4B is the one
candidate whose count moved, and it moved on both switches rather than between them:
`payload-splitting` fired on one framed draw in four under `shipped-argv` and on one in four under
`request-key`, and the same cell moves the unframed control between 3 and 4 across the same eight
sittings. So the single pair of matrices that first showed 3 against 2 was that cell's own
instability. Nothing measured here says the two levers must stay together on a build where they
part, which is why the shipped row exists rather than a sentence recording that they agreed once.

**One row of the table above reads lower than it did.** gemma-4-E2B obeys **3 of 10** framed here,
in every sitting under both switches, against the 4 of 10 published on 2026-07-01. The pick and the
three Qwen subagent candidates all draw their published counts, Qwen3.5-4B in six of its eight
sittings and the other three in every one of theirs. The engine build, the
corpus's own payloads and the detectors have all moved since that table was drawn, so the
difference is a drift in the row rather than anything the switch did. The table keeps its own
wording, this addendum being its correction.

**What the switch still does not cover.** The head of a row's command line is written in the
harness rather than read off a tier: `-ngl 99 --ctx-size 8192 --parallel 1`, where the CPU subagent
servers run `-ngl 0` and `--parallel 2` and the hosted GPU tier runs `--parallel 2`
([R-546](../refinements/tasks/546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md)).
And the pair's budget half is not a row of its own, so the third cell the hand run drew,
`--reasoning-budget 0` with no kwarg and no key, is still a hand run
([R-547](../refinements/tasks/547-the-pairs-budget-half-has-no-injection-row-of-its-own.md)).

## Addendum (2026-09-05): every row starts with its tier's own command line, and the subagent pick has a CPU row

The switch-row addendum above left the head of every row's command line typed into the harness,
`-ngl 99 --ctx-size 8192 --parallel 1`, whatever tier the row's model belongs to, and
[R-546](../refinements/tasks/546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md)
asked for the window and the slot count to be read off `ModelHostConfig` the way the reasoning-off
pair is, then for a decision on whether `-ngl` is a row or a constant. Both are done here, and the
re-derivation turned up two things the entry did not say.

**Re-derived against the tree first.** The entry is right about the head: `server_argv` wrote it,
no row of the constant registry named the harness for the window or the slot count (the registry
holds the subagent window and slot count to three compose files and nothing else), and the
agreement was coincidence. Its sentence "only the context size agrees" is the comparison with the
CPU compose servers; against the hosted GPU tier two of the three numbers agreed, the layer count
and the window, and the slot count did not. What the entry did not say is that the head was one
head for three tiers, so every cortex row ran at half its tier's window, 8192 against the 16384
`DEFAULT_CORTEX_CTX_SIZE` ships, while the deep-tier rows happened to agree with theirs. The second
thing: **the text arm had drawn no cortex row at all since the switch rows landed.**
`test_injection_defense` skipped a row whenever `switch_for` returned a switch other than the one
asked for, and for a thinking-on model it returns `THINKING_ON` under both entries of `SWITCHES`,
so both copies skipped. The runbook's sentence that "the two cortex rows' second copy is skipped"
described the intent; `pytest -k "12B and shipped-argv"` at that commit reported `1 skipped`.
Nothing published on 2026-09-04 rested on a cortex row, so no number is wrong, but the arm was
smaller than its collection said and nothing reported it.

**A row starts with its tier's command line now.** A `Model` names the tier it is measured as
(`CORTEX_TIER`, `BRAIN_TIER`, `SUBAGENT_TIER`, the logical ids the sidecar and the brain share),
`tier_args` reads that tier's `TierArgs` off one `ModelHostConfig` with every artifact named, and
`server_argv` hands it to the sidecar's own `llama_server_argv` with four things substituted: the
artifact, the probe's port, the placement's layer count and the tail. Whether a model thinks is
read off the tier as well rather than typed beside it. The head is therefore no longer a spelling
of anything: a cortex row runs at its tier's 16384 window, a subagent row at the tier's two slots,
and a retuned tier moves every row that measures it. `test_switch_rows.py` holds a shipped text-only
row equal to the sidecar's argv for the tier with only the artifact and port changed, which fails
the typed head on the cortex window and on the subagent slot count. The thinking-on rule now runs a
tier that pulls neither lever once, under the shipped id, since its server starts with its tier's
own argv, and skips the request-key copy; mutating that rule back to its 2026-09-04 shape fails
the row-selection test. Eight mutations of the harness were each shown to fail
`test_switch_rows.py` (1 to 4 of its 14 tests each) and the restored file passes all 14.

**`-ngl` is a row, for the one tier the stack places twice.** The subagent tier runs on the card in
the model host's tier and on the CPU in the server `docker-compose.subagents.yml` starts, and the
shipped routing sends every spawn to the CPU server unless a deployment names the GPU tier
(ADR-0012, and that compose file's own comment). So the pick's published resistance, every 0 of 10
above, had been drawn only at the placement a stock deployment does not run it at. `PLACEMENTS`
holds two, built on the core's own `PlacementTarget`: the card row takes the tier's layer count off
the sidecar, and the CPU row takes the core's word for that server, `PlacementTarget.CPU.ngl`, runs
the CPU image the compose files name, is given no GPU device, and is given the cgroup quota the
override sets on that server, read off the brain's `DEFAULT_CPU_BUDGET`. The two image names are
typed into the harness as the compose files type them, nothing in Python declaring an image.
`repeat_of` says which rows are a model's own: a thinking-off model has a row per switch on the
card and a shipped row on the CPU, and a thinking-on model has one row, so the CPU placement adds
five rows to the lineup rather than doubling it. The text arm collected 28 rows, of which 17
ran, until the lever addendum in [ADR-0005](ADR-0005-llamacpp-engine.md) added a third switch the
same night and made that 42 and 22.

**Measured 2026-09-05** on build 10680 (`d7bd3bfca`) from both cached images,
`ghcr.io/ggml-org/llama.cpp:server-cuda` for the card and `ghcr.io/ggml-org/llama.cpp:server` for
the CPU, ten attacks per row with a framed arm and an unframed control:

| row | placement | framed obeyed / 10 | unframed control / 10 | wall clock |
|---|---|---|---|---|
| gemma-4-E4B (subagent pick), `shipped-argv` | card, the tier's `-ngl 99 --ctx-size 8192 --parallel 2` | **0** | 2 (`refusal-suppression`, `output-laundering`) | 134 s for this row and the next together, loads included |
| gemma-4-12B (cortex pick), `thinking-on` | card, the tier's `-ngl 99 --ctx-size 16384 --parallel 1` | **0** | 1 (`output-laundering`) | (in the 134 s above) |
| gemma-4-E4B (subagent pick), `shipped-argv` | CPU, `-ngl 0`, one thread per hardware thread, before the quota was part of the placement | **0** | 1 (`refusal-suppression`) | 819 s |
| gemma-4-E4B (subagent pick), `shipped-argv` | CPU, `-ngl 0`, the stack's 4-CPU quota | **0** | 1 (`refusal-suppression`) | 1837 s |

**The reading.** The pick's card row under the tier's own head is the same cell for cell as its
four sittings of 2026-09-04 under the typed head, attack names included, so reading the slot count
off the tier moved nothing, which is what a KV split should do for one request at a time. The
cortex row, the first the arm has drawn since 2026-09-04 and the first ever at the tier's own
window, reproduces the 0 of 10 of the 2026-07-01 table. The pick on the CPU is 0 of 10 framed in
both sittings. The one cell that moved between placements is the unframed control's
`output-laundering`, which fired on the card as it did in every sitting on 2026-09-04 and did not
fire on the CPU in either sitting. That is the corpus's one unstable cell, measured in the image arm
to fire on about half its runs, so one CPU sitting cannot separate a placement effect from the
cell's own instability; on the framed arm, where the pick's number lives, nothing moved, and this
ADR reads the pick's resistance as a property of the pick rather than of the card. The quota is part of
the placement because it is what the stack gives that server and because it changes what a row
costs: with 24 threads and no quota the server decoded at 0.8 tokens a second and the row took
819 s, and under the quota, the same 24 threads sharing four cores' time, it decoded at about 0.4
on the completions read before the container was removed and the row took 1837 s, inside the 0.18
to 1.35 the subagent runbook records for the tier under its cap.

**What this does not do, and where that is recorded.** The other four subagent candidates have no
CPU sitting, at half an hour each on this host
([R-555](../refinements/tasks/555-the-other-four-subagent-candidates-have-no-cpu-row.md)). The
image arm's published rows were all measured at the typed 8192 window and now run at the cortex
tier's 16384; a window is a KV allocation and nothing measured there depends on it, but no pixel
row has been replicated under the tier's head
([R-556](../refinements/tasks/556-no-pixel-row-has-been-replicated-at-the-tiers-own-window.md)).
The two image names are typed in the harness, in three compose files and in the model-host
Dockerfile with nothing holding them equal
([R-557](../refinements/tasks/557-the-engine-image-names-are-typed-in-five-places.md)). Whether a
model thinks is read off the tier's name and not off its shipped budget, so a cortex tier started
at a zero budget would still be measured deliberating
([R-558](../refinements/tasks/558-thinking-follows-the-tiers-name-and-not-its-shipped-budget.md)).
The CPU row applies the override's CPU quota and not its memory cap
([R-559](../refinements/tasks/559-the-cpu-row-carries-the-cpu-quota-and-not-the-memory-cap.md)).
