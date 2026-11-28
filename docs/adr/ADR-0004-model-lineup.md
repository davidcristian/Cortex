# ADR-0004: Model lineup

**Status:** Accepted (2026-11-20)

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
   | Cortex | `gemma-4-12B-it-qat` (pick), `Qwen3.5-9B-Q4_K_M` (alternate) |
   | Subagent | `gemma-4-E4B-it-qat` (pick), `Qwen3.5-2B-Q4_K_M` (alternate on a second CPU server), `gemma-4-E2B-it-qat`, `Qwen3.5-0.8B-Q8_0`, `Qwen3.5-4B-Q4_K_M` |
   | Deep | `Qwen3.8-27B-UD-Q4_K_M` (pick), `gemma-4-31B-it-qat` (alternate), `Qwen3.6-35B-A3B-UD-Q3_K_XL`, `gemma-4-26B-A4B-it-qat`, `Qwen3.8-Flash-Next-UD-Q4_K_XL` |
   | Embedder | `nomic-embed-text-v1.5` Q8_0 (pick), `nomic-embed-text-v2-moe` (alternate) |

   Each gemma entry is the `UD-Q4_K_XL` file of `unsloth/gemma-4-<size>-it-qat-GGUF`, which stores
   the quantization-aware-trained weights as `Q4_0`. The rows this record cites were drawn on
   Google's `q4_0` files of those weights, on earlier Qwen3.5 and Qwen3.6 files and on
   Qwen3.8-Flash-Next at `UD-Q3_K_XL`, none of which the mount still holds, and both gemma chat
   templates have changed since ([R-1238](../refinements/tasks/1238-the-lineups-readings-were-drawn-on-files-the-mount-no-longer-holds.md)).

6. **Cortex: gemma-4-12B QAT q4_0 with its projector.** Both multimodal candidates cost about the
   same VRAM with their projectors, so VRAM did not decide it; gemma is the stronger chat model and
   is quantization-aware trained, so its 4-bit weights hold quality better than a post-hoc quant.
   Injection resistance did not decide it. At the engine's sampler, as the tier runs, the pick obeys
   0 of 100 framed draws against 16 of 100 unframed, and the alternate 7 of 100 against 40
   ([injection text rows](../readings/injection-text-rows.md)), measured as its `UD-Q4_K_XL`. The
   alternate's template drops a third leading system message, so the adapter sends it a turn's
   preamble, memory and recap joined into one.

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

8. **Deep: Qwen3.8-27B `UD-Q4_K_M`; gemma-4-31B QAT q4_0 is the alternate.** What decides is whether
   the file fits whole on the card inside the model budget, 18,177 MiB at the highest reading of a
   row; the other axes do not separate the two. The pick's file fits whole up to 24K drafting with
   the layer in its own file and 40K without ([readings](../readings/nvfp4-deep-tier.md)), and the tier started on it at 16K
   and `q8_0` read 16,991 MiB above the card's floor at its highest ([R-1243](../refinements/tasks/1243-every-tier-holds-its-context-in-the-default-16-bit-cache.md)). The alternate's
   file fits whole at no context at 16 bits ([readings](../readings/kv-cache-every-model.md)): started as the model host starts the
   tier, at 16K with every layer on the card, it read 18,375 to 19,774 MiB above the floor over
   eight launches, and fits the budget with layer 0 in RAM (`CORTEX_NGL_BRAIN=60`)
   ([readings](../readings/kv-cache-deep-whole.md#other-shapes-at-the-budget)). On four written questions at the shipped 16384 context, the pick stopped on 11
   of 12 draws at its template's own effort (`xhigh`), 12 with its draft layer and 12 at `medium`
   with and without it, the alternate on 12 ([readings](../readings/deep-candidates.md#the-stop-rows-at-16384)). Behind a full handoff prompt, which
   leaves 5,584 of those tokens, the drafted pick stopped on 11 of 12 at `medium` and at `xhigh`,
   the alternate's `UD-Q4_K_XL` file on 9, a cost a deployment naming it accepts, and on 10 with a
   window 10,000 characters shorter ([readings](../readings/deep-handoff-room.md)). At 8192 the alternate stopped on 11,
   Qwen3.6-35B-A3B (at `UD-Q3_K_XL`) on 6 and gemma-4-26B-A4B on 5, the one count apart. At the
   engine's sampler, thinking on, the pick at the shipped 16384 and `q8_0` obeys 0 of 100 framed
   injection draws against 0 unframed, at `xhigh` with its draft layer and without and at `medium`
   with it, and the alternate 0 against 8 at 8192. The pick has three costs: a median of 2378
   reasoning tokens a draw at the default `medium` with its draft layer, 1182.5 without, against the
   alternate's 1434 ([readings](../readings/deep-effort.md)); no QAT weights and none of the cortex's family, template or
   prompt idiom; and a preserve flag the tier cannot set ([R-1276](../refinements/tasks/1276-the-deep-tier-never-sends-the-templates-preserve-flag.md)). The two mixture-of-experts
   entries decode about four times as fast as the alternate, but each draw of theirs that did not
   stop filled the context reasoning. Qwen3.8-Flash-Next fits neither the card nor this machine's
   memory, and whether it stops was not drawn. The deep tier has no default artifact: a deployment
   names the pick to start it.

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
    deliberate soft cap of 16 GB (`CORTEX_VRAM_SOFT_CAP_GB`), the owner's policy about the card
    rather than a measurement; the cortex's measured footprint, `CORTEX_VRAM_CORTEX_GB` at 8.9, is
    ADR-0012's. Context is set explicitly, never left to llama-server's default of the model's
    maximum across four slots: the cortex runs 16384 tokens in one slot (`CORTEX_CTX_SIZE`), the
    deep tier the same 16384 in one (`CORTEX_CTX_SIZE_BRAIN`, 664 to 667 MiB more than 8192 on
    gemma-4-31B), because both phases read one history window
    ([ADR-0014](ADR-0014-history-windowing.md) decision 8), and a subagent server 8192 over two slots.

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

14. **The deep tier takes its multi-token-prediction drafter from one setting, named with the
    deep file.** `CORTEX_MODEL_FILE_BRAIN_DRAFT` is a path under the models mount. The pick has
    its draft layer inside its own file, so a deployment of it gives the setting the same path
    as `CORTEX_MODEL_FILE_BRAIN`: `drafter_flags` then appends `--spec-type draft-mtp
    --spec-draft-n-max 3` to the deep tier's argv with no `--model-draft`, and the engine drafts
    with that layer without loading the model twice. Any other path is a drafter file
    (`unsloth/gemma-4-31B-it-qat-GGUF/mtp-gemma-4-31B-it-Q8_0.gguf` for the alternate) and
    appends `--model-draft PATH` before those four items. A path without the type drafts
    nothing. The flags are passed through the tier's `extra`, since the model host's argv
    builder has exactly one splat and `scripts/hostedtiers.py` reads it that way. The pick's
    layer wrote at 1.75 times its no-draft rate at 24K and a draft length of 3
    ([readings](../readings/nvfp4-deep-tier.md)). Measured as its `F16` build, at matched power
    limits the alternate's drafter decodes 1.34 times the plain rate on a tool-call turn and on
    answer text and 1.86 to 1.89 times on a reasoning trace, for about 1000 MiB and about a
    tenth more load time. The setting has an empty default: a compose default would append it
    to whatever deep model a deployment names, and `${VAR:-default}` cannot be turned off by an
    empty value. The model-swap runbook and the gpu override name it as part of the pick's
    configuration, with the settings that move with it: `CORTEX_SWAP_BRAIN_VRAM_MIB` raised by
    the drafter's cost, the GPU subagent tier listed in `CORTEX_SWAP_EVICT_MODELS`,
    `CORTEX_SWAP_CORESIDENT` left off, and the decode minimum measured again with the drafter
    drafting. The cortex and the GPU subagent tier have drafter settings of their own, which
    default to the drafter beside a lineup file ([ADR-0077](ADR-0077-model-card-settings.md) decision 7).

## Consequences

- The picks are named in `docker/docker-compose.gpu.yml`, `docker-compose.subagents.yml`,
  `docker-compose.subagents-roster.yml` and `docker-compose.memory.yml` as the defaults of their
  `CORTEX_MODEL_FILE_` variables, and in the model host's settings; changing a pick means changing
  those defaults and this record together.
- gemma-4-31B, the GPU subagent tier and the drafter do not fit one 24 GB card, and beside that
  tier's two default servers the pick does not fit either, so co-residency stays off. Under the deployed handoff the pool is
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
- The two older mixture-of-experts entries and Qwen3.8-Flash-Next have no injection row. The
  pick's rows were drawn at its template's `xhigh` and at the default `medium`; `low` has none.
- The injection measurements for a candidate start from the tier's deployed configuration
  ([ADR-0060](ADR-0060-injection-rows-follow-the-tier.md)).

## Alternatives rejected

- **Picking the cortex on VRAM**: both candidates cost about the same with their projectors.
- **gemma-4-31B as the deep pick, for its family and its shorter reasoning**: at 16K with every
  layer on the card it is over the model budget at both cache types (decision 8).
- **A mixture-of-experts deep model for its decode rate**: gemma-4-26B-A4B stops less often than
  gemma-4-31B, and Qwen3.6-35B-A3B, whose count does not read apart, stopped on no draw of two
  of the four questions; Qwen3.8-Flash-Next misses the stall bound before its first token.
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
  [ADR-0060](ADR-0060-injection-rows-follow-the-tier.md), [ADR-0077](ADR-0077-model-card-settings.md).
- Runbooks: [llamacpp-gpu](../runbooks/llamacpp-gpu.md),
  [subagents-cpu](../runbooks/subagents-cpu.md), [model-swap](../runbooks/model-swap.md),
  [memory-pgvector](../runbooks/memory-pgvector.md).
- Modules: [brain-model-manager](../modules/brain-model-manager.md),
  [brain-memory](../modules/brain-memory.md).
- Readings: [model lineup](../readings/model-lineup.md), [deep
  candidates](../readings/deep-candidates.md), [Qwen3.8-Flash-Next](../readings/flash-next.md),
  [injection text rows](../readings/injection-text-rows.md), [subagent CPU
  rows](../readings/subagent-cpu-rows.md).
