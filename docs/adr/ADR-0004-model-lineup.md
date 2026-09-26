# ADR-0004: Model lineup

**Status:** Accepted (2026-09-26)

## Context

Three model tiers share one 24 GB card ([ADR-0001](ADR-0001-architecture.md)): a resident, natively
multimodal cortex; small subagents; and an on-demand deep model that evicts the others. An embedder
serves memory beside them. Each tier needs a pick from the candidates already on the host, an
artifact and quantization, a placement, and the flags that make its server behave as the design
assumes. The candidates were fixed first and the picks measured afterwards, on VRAM, load time,
decode rate, whether a reasoning model stops, resistance to prompt injection, and what each entry's
chat template does with the thinking switch. The measurements are in [model
lineup](../readings/model-lineup.md), [deep candidates](../readings/deep-candidates.md) and
[injection text rows](../readings/injection-text-rows.md).

## Decision

### Engine, ids and artifacts

1. **Every artifact is GGUF, served by llama.cpp** ([ADR-0005](ADR-0005-llamacpp-engine.md)).

2. **The core uses logical model ids, never file paths.** `cortex`, `subagent`, `brain` and the ids
   derived from them (`subagent-gpu`) are the only names that cross a port or the model host's
   control API. Only an adapter or the model host maps an id to an artifact, a port, a layer count
   or a context size.

3. **Models stay on the host, mounted read-only, never copied.** Every service that loads a model
   bind-mounts `CORTEX_MODELS_DIR` read-only, and every artifact is named under it by a
   `CORTEX_MODEL_FILE_` variable (`CORTEX`, `CORTEX_MMPROJ`, `BRAIN`, `BRAIN_DRAFT`, `SUBAGENT`,
   `SUBAGENT_GPU`, `SUBAGENT_QWEN`, `EMBED`), which `scripts/flagcheck.py` requires
   ([ADR-0043](ADR-0043-subagent-server-flags.md)). A cold load is limited by the mount's read
   rate; copying hot models off the mount is the option if a swap ever feels slow.

4. **The embedding column stays dimension-agnostic, and no ANN index is deployed.**
   `memories.embedding` is an unbounded `vector`, so adopting an embedder of another width is one
   variable. `hnsw` and `ivfflat` both need a typmod, which would turn an embedder change into a
   migration this repo has no runner for, and the measured `hnsw` index kept on average only about
   half of the exact top 20, a loss nobody has yet explained. The exact scan is cheap at personal
   scale and grows linearly, passing a recalling turn's whole time to first token at about 75,000
   memories in the global scope ([R-095](../refinements/tasks/095-ann-index.md) applies at that
   count, which the recall log line reports as `available`); calibrating the index against the
   exact scores is the first step then.

### Candidates and picks

5. **The candidate sets are fixed.** New entries need a new decision.

   | Tier | Candidates |
   |---|---|
   | Cortex | `gemma-4-12B-it-qat-q4_0` (pick), `Qwen3.5-9B` 4-bit (alternate) |
   | Subagent | `gemma-4-E4B-it-qat-q4_0` (pick), `Qwen3.5-2B-Q4_K_M` (alternate on a second CPU server), `gemma-4-E2B-it-qat-q4_0`, `Qwen3.5-0.8B-Q8_0`, `Qwen3.5-4B-Q4_K_M` |
   | Deep | `gemma-4-31B-it-qat-q4_0` (pick), `Qwen3.6-27B-Q4_K_M` (alternate), `Qwen3.6-35B-A3B-UD-Q3_K_M`, `gemma-4-26B-A4B-it-qat-q4_0`, `Qwen3.8-27B-UD-Q4_K_M`, `Qwen3.8-Flash-Next-UD-Q3_K_XL` |
   | Embedder | `nomic-embed-text-v1.5` Q8_0 (pick), `nomic-embed-text-v2-moe` (alternate) |

6. **Cortex: gemma-4-12B QAT q4_0 with its projector.** Both multimodal candidates cost about the
   same VRAM with their projectors, so VRAM did not decide it; gemma is the stronger chat model and
   is quantization-aware trained, so its 4-bit weights hold quality better than a post-hoc quant.
   Injection resistance did not decide it. At the engine's sampler, as the tier runs, the pick obeys
   0 of 100 framed draws against 16 of 100 unframed, and the alternate 7 of 100 against 40
   ([injection text rows](../readings/injection-text-rows.md)). The alternate is measured as
   `Qwen3.5-9B-UD-Q4_K_XL.gguf`, the 4-bit quant the mount holds, since the `Q4_K_M` the candidate
   set first named is not there. Its template refuses a second leading system message, so the
   adapter sends it a turn's preamble, memory and recap joined into one.

7. **Subagent: gemma-4-E4B QAT q4_0.** It was picked when, at temperature 0, it obeyed 0 of 10
   framed injections on both placements. At the engine's sampler, as the tier runs, it obeys 9 of
   100 framed draws on the card and 10 on the CPU, against 22 and 24 unframed, where gemma-4-E2B
   obeys 28 and 25 and the three Qwen candidates 8 to 10 and 8 to 12, so on both placements the pick
   leads gemma-4-E2B only ([injection text rows](../readings/injection-text-rows.md), [subagent CPU
   rows](../readings/subagent-cpu-rows.md)). Injection resistance was adopted as
   a selection axis at a measured cost: against the Qwen3.5-2B it replaced, about 2.6 times the
   load, 3 times a narrow task's latency and 2.8 times the resident memory, acceptable for narrow
   asynchronous work. The safety default of [ADR-0017](ADR-0017-subagent-model-safety.md) is tied to
   this pick by its logical id, so a revision here moves that default with it. Qwen3.5-2B stays the
   second CPU server (`CORTEX_MODEL_FILE_SUBAGENT_QWEN`,
   [ADR-0018](ADR-0018-heterogeneous-subagents.md)) and the cheap override when latency matters more
   than injection resistance. The five entries do the same narrow work at widely different rates
   under the constrained reply path ([ADR-0028](ADR-0028-grammar-constrained-subagents.md)); the
   subagent runbook's override table says what each costs, and gemma-4-E2B and Qwen3.5-0.8B are the
   two to override to last.

8. **Deep: gemma-4-31B QAT q4_0.** What decides is whether the model reaches its answer inside the
   deployed context with no limit set, which is how the tier runs; VRAM decides nothing among the
   entries that fit the card alone. The two older mixture-of-experts entries decode about 2.6 times
   as fast and spent the whole context reasoning, returning an empty reply (build `b10236`, on
   questions no longer recorded). Qwen3.8-Flash-Next fits neither the card nor this machine's
   memory: with 13 layers of experts on the card and the rest read from the models mount it loads
   inside the swap bound, but under a 20 GiB memory cap it sent no first token for a 6184-token
   prompt within twice the stall bound, so it cannot serve this tier here; its first token at the
   shipped cap and whether it stops were not drawn
   ([R-735](../refinements/tasks/735-flash-nexts-feasibility-row-is-not-complete-at-the-shipped-memory-cap.md)).
   On four written questions drawn on one build and day, three seeds each, the pick stopped on 11 of
   12, Qwen3.8-27B on 10 at its default effort (`xhigh`) and on 12 at `low` and at `medium`, and the
   alternate on 10; no count reads apart from the pick's. The pick reasons least of the three at
   their defaults (a median of 1434 tokens against 2189 and 4118), is QAT, and shares the cortex's
   family, template and prompt idiom. Qwen3.8-27B costs 0.82 of its VRAM at the same decode rate and
   has a drafter built in, and deploying it needs settings the tier lacks, an effort level first
   ([R-738](../refinements/tasks/738-the-deep-tier-cannot-set-a-templates-reasoning-effort-or-preserve-flag.md)).
   Qwen3.6-27B is the documented alternate, one `CORTEX_MODEL_FILE_BRAIN` away, for a deployment
   that wants about 2.7 GB more of the card free during a handoff; its template drops a third
   leading system message, so the adapter joins a deep turn's preamble, memory and recap into one
   before sending ([ADR-0071](ADR-0071-leading-system-messages.md)).
   The deep tier has no default artifact: a deployment turns it on by naming the pick. At the
   engine's sampler, thinking on, the pick obeys 0 of 100 framed injection draws against 8 of 100
   unframed, and Qwen3.8-27B 0 against 0.

9. **Embedder: nomic-embed-text-v1.5 Q8_0**, 768-dimensional, on the CPU (`-ngl 0`), negligible in
   memory. `nomic-embed-text-v2-moe` is the multilingual alternative. The override is
   `CORTEX_MODEL_FILE_EMBED`, named in the artifact family like every other model; the old
   `CORTEX_EMBED_MODEL_FILE` is read by nothing. The embedder is excluded from injection
   measurement, since it emits vectors.

10. **A candidate's chat template is a selection input, read before a pick.** Every chat entry drawn
    respects the thinking switch on a plain request. Under a `response_format` the lineup splits
    inside a family: the dense gemma-4 entries and every Qwen entry respect it, and both gemma-4-E
    entries reason through it anyway. Asked for its rendered prompt with the kwarg and without it
    (`POST /apply-template`), an entry whose template renders a thought already closed respects the
    switch, and one that drops the block and adds nothing does not; that column has predicted which
    entries write into the reasoning channel, which a delegated run discards on every entry
    measured. The subagent tier's two reasoning-off flags stay, since the pair covers both kinds of
    entry ([ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md)).

### Placement, context and the CPU tier

11. **Placement and budget.** The cortex is GPU-resident; the embedder runs on the CPU; subagents
    are GPU-first with CPU overflow ([ADR-0012](ADR-0012-resource-governance.md)); the deep model
    swaps in for a handoff ([ADR-0030](ADR-0030-brain-handoff.md)) and needs no hybrid layer split
    on this card, which stays the option for a smaller one. The AI stack's GPU budget is a
    deliberate soft cap of 14 GB (`CORTEX_VRAM_SOFT_CAP_GB`), the owner's policy about the card
    rather than a measurement; the cortex's measured footprint, `CORTEX_VRAM_CORTEX_GB` at 8.6, is
    ADR-0012's. Context is set explicitly, never left to llama-server's default of the model's
    maximum across four slots: the cortex runs 16384 tokens in one slot (`CORTEX_CTX_SIZE`), the
    deep tier 8192 in one (`CORTEX_CTX_SIZE_BRAIN`, doubling it costs well under a gigabyte), and a
    subagent server 8192 over two slots.

12. **A CPU subagent server's thread count is set to its CPU quota.** Both CPU servers pass
    `--threads "${CORTEX_SUBAGENTS_CPU_BUDGET:-4.0}"`, the substitution their `cpus` cap reads, so
    a deployment cannot move the count without moving the cap. Left to its default the engine
    starts one thread per hardware thread inside the quota, the threads are throttled mid-step at
    the engine's barriers, and the same run took 13.7 times as long on identical output. The engine
    rounds a fractional count down, which is the safe direction; a budget under one CPU rounds down
    to 0, which the engine reads as its own default
    ([R-636](../refinements/tasks/636-a-cpu-budget-under-one-floors-the-thread-count-to-the-engines-default.md)).
    No `--threads-batch` is set, so the prompt rate follows the same count. `crosscheck.py` compares
    each deployed file's flag line and count as one search text, and `flagcheck.py` requires a
    `--threads` on every server started with `-ngl 0`
    ([ADR-0043](ADR-0043-subagent-server-flags.md)); what no check covers is the count's value on a
    third CPU server
    ([R-676](../refinements/tasks/676-a-third-compose-files-thread-count-is-held-to-no-value.md)).

13. **A CPU subagent server runs under an 8 GiB memory cap with swap disabled.** The cgroup is
    charged for the mapped artifact as well as the working set, so the pick's server sits at about
    nine tenths of the cap once loaded; `docker stats` hides the mapped half. Under a delegated run
    at the deployed cap and two slots the cap does not bind and nothing is reclaimed. It fits this
    pick and says nothing about a larger artifact
    ([R-675](../refinements/tasks/675-the-subagent-memory-cap-is-sized-for-the-picks-artifact-alone.md)).

### The deep tier's drafter

14. **The deep pick takes its multi-token-prediction drafter from one setting, recommended with the
    pick.** `CORTEX_MODEL_FILE_BRAIN_DRAFT` names the drafter under the models mount
    (`google/gemma-4-31B-it-assistant/assistant-F16.gguf` for the pick). A named file appends
    `--model-draft PATH --spec-type draft-mtp` to the deep tier's argv after its usual end, and
    `drafter_flags` in `tiers.py` returns the four items or none, because the path without the type
    loads the drafter and drafts nothing. The pair is passed through the tier's `extra`, since the
    model host's argv builder has exactly one splat and `scripts/hostedtiers.py` reads it that way.
    At matched power limits the drafter decodes 1.34 times the plain rate on a tool-call turn and
    on answer text, and 1.86 to 1.89 times on a reasoning trace; it costs about 1000 MiB and about
    a tenth more load time, which a handoff recovers within about 400 to 1500 decoded tokens. The
    setting has an empty default: it serves one pick, a compose default would append it to whatever
    deep model a deployment names, and `${VAR:-default}` cannot be turned off by an empty value.
    The model-swap runbook and the gpu override name it as part of the pick's configuration, with
    the settings that move with it: `CORTEX_SWAP_BRAIN_VRAM_MIB` raised by the drafter's cost, the
    GPU subagent tier listed in `CORTEX_SWAP_EVICT_MODELS`, `CORTEX_SWAP_CORESIDENT` left off, and
    the decode minimum measured again with the drafter drafting. Only the deep tier reads the
    setting; nothing on the mount drafts for the cortex or the subagent pick. Qwen3.8-27B has a
    multi-token-prediction layer in its own file, which the engine drafts with on
    `--spec-type draft-mtp` alone, at 1.40 to 1.43 times the plain rate on reasoning and tool-call
    turns and 1.16 on answer text, for about 950 MiB; the setting names a separate file, so a
    deployment of that entry drafts nothing
    ([R-739](../refinements/tasks/739-the-deep-tier-cannot-name-a-drafter-built-into-its-own-model.md)).

## Consequences

- The picks are named in `docker/docker-compose.gpu.yml`, `docker-compose.subagents.yml`,
  `docker-compose.subagents-roster.yml` and `docker-compose.memory.yml` as the defaults of their
  `CORTEX_MODEL_FILE_` variables, and in the model host's settings; changing a pick means changing
  those defaults and this record together.
- With the drafter, the deep model, the GPU subagent tier and the drafter do not fit one 24 GB
  card, so the drafter rules out co-residency on this card. Under the deployed handoff the pool is
  drained and the evicted tier costs nothing in use. A deployment that names the drafter raises its
  declared cost by the drafter's, because the fit check compares the card against that figure alone
  and the brain cannot see a drafter through the `ModelHost` port
  ([ADR-0055](ADR-0055-co-residency-and-spill-watch.md) decision 2,
  [R-709](../refinements/tasks/709-the-fit-check-does-not-count-the-deep-tiers-drafter.md)). The
  spill watch reports a drafter-sized overcommit on a tool-call turn and not on a reasoning trace,
  which the drafter speeds most ([co-residency readings](../readings/co-residency.md)).
- The delegated-run limits were sized on the CPU tier before its thread count was set, and are
  looser than their derivation asked for now that it is; they are re-sized only on whole-subtask
  measurements
  ([R-637](../refinements/tasks/637-the-delegated-run-ceilings-were-sized-on-the-unpinned-cpu-tier.md)).
- The alternate, the two older mixture-of-experts entries and Qwen3.8-Flash-Next have no injection
  row, and an adopted alternate needs its own. Qwen3.8-27B's row was drawn at its template's default
  effort, so a deployment that sets another effort draws it again.
- The injection measurements for a candidate start from the tier's deployed configuration
  ([ADR-0060](ADR-0060-injection-rows-follow-the-tier.md)).

## Alternatives rejected

- **Picking the cortex or the deep tier on VRAM**: every candidate but Qwen3.8-Flash-Next fits the
  card alone, so VRAM separates none of them.
- **A mixture-of-experts deep model for its decode rate**: the two that fit the card spent the
  whole deployed context reasoning and replied with nothing
  ([R-742](../refinements/tasks/742-the-mixture-of-experts-rejection-rests-on-unrecorded-questions.md)),
  and Qwen3.8-Flash-Next, paged from the mount, misses the stall bound before its first token.
- **An ANN index now**: see decision 4. **Storing the vector inline** (`SET STORAGE PLAIN`) bought a
  fifth of the scan back and grew the table, the arithmetic rather than the detoasting being most
  of the cost.
- **A drafter field of its own on `TierArgs`, or the drafter on by default**: see decision 14.
- **Checking the thread count's value in `flagcheck.py`**: a CPU quota exists only on a compose
  service, and the model host's GPU tier has none for a count to equal.

## Related

- [ADR-0005](ADR-0005-llamacpp-engine.md), [ADR-0012](ADR-0012-resource-governance.md),
  [ADR-0013](ADR-0013-untrusted-content.md), [ADR-0017](ADR-0017-subagent-model-safety.md),
  [ADR-0018](ADR-0018-heterogeneous-subagents.md),
  [ADR-0028](ADR-0028-grammar-constrained-subagents.md), [ADR-0030](ADR-0030-brain-handoff.md),
  [ADR-0043](ADR-0043-subagent-server-flags.md),
  [ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md),
  [ADR-0059](ADR-0059-prompt-cache-per-tier.md),
  [ADR-0060](ADR-0060-injection-rows-follow-the-tier.md).
- Runbooks: [llamacpp-gpu](../runbooks/llamacpp-gpu.md),
  [subagents-cpu](../runbooks/subagents-cpu.md), [model-swap](../runbooks/model-swap.md),
  [memory-pgvector](../runbooks/memory-pgvector.md).
- Modules: [brain-model-manager](../modules/brain-model-manager.md),
  [brain-memory](../modules/brain-memory.md).
- Readings: [model lineup](../readings/model-lineup.md), [deep
  candidates](../readings/deep-candidates.md), [injection text
  rows](../readings/injection-text-rows.md), [subagent CPU rows](../readings/subagent-cpu-rows.md).
