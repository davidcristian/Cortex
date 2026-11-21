# ADR-0077: Model card settings and what each tier runs

**Status:** Accepted (2026-11-20)

## Context

A model's publisher recommends settings on its model card: a sampler, the flags that start its
multi-token-prediction drafter, and for some models a flash attention setting, an image token
budget, a context size or an input prefix. Until this record nothing in the repo said what the
cards recommend, which of those values a tier already runs, or why a tier differs from its card.

The stack sets no sampler. No server starts with a sampler flag and the brain sends no sampler
field, and the probes send none either ([ADR-0041](ADR-0041-injection-image-variant.md) decision
7). The engine then takes the sampler from the model file: a GGUF header can hold
`general.sampling.temp`, `general.sampling.top_p` and `general.sampling.top_k`, and the engine uses
its own default for a value the file leaves out. That is what a reading means by "the engine's
sampler", and `GET /props` reports the result.

The cards were read on 2026-11-16, when the models mount moved to the files
[ADR-0004](ADR-0004-model-lineup.md) names. The headers of those files were read the same day.

## Decision

1. **A tier's sampler is the one its model file sets, with the engine's default for the rest.** The
   stack adds no sampler flag and no sampler field. A publisher that writes its card's sampler into
   the file is followed with no setting here, and the injection, stop and reply rows of an entry
   stay comparable with each other, since each was drawn this way.

2. **The model card is the reference, and this record keeps what each card recommends.** A card is
   read when a file joins the candidate set of ADR-0004 and when a pick's file changes. Decisions 4
   to 6 are edited in place, and the Context names the day the cards were last read.

3. **A tier moves a setting toward its card only after a draw on this machine compares the two.**
   The picks were chosen on rows drawn at the settings the tiers run, so a new setting needs its
   own rows first. Until then the tier keeps what it runs, and decision 6 lists the difference
   with the task that would close it or the reason it is kept.

4. **Sampling: what the card recommends, what the file sets and what the tier runs.** Values are
   temperature, `top_p` and `top_k` in that order, then `min_p` and the presence penalty where a
   card names them.

   | Entries | The card recommends | The file sets | The tier runs |
   |---|---|---|---|
   | gemma-4 12B, E4B, E2B, 26B-A4B, 31B | 1.0, 0.95, 64 for every use; no `min_p` or penalty named | 1.0, 0.95, 64 | the card's three values, and the engine's `min_p` |
   | Qwen3.8-27B, Qwen3.8-Flash-Next | thinking on: 1.0, 0.95, 20, `min_p` 0, no penalty. Thinking off: 0.7, 0.8, 20, `min_p` 0, penalty 1.5 | 1.0, 0.95, 20 | the card's thinking-on values, except the engine's `min_p` |
   | Qwen3.6-35B-A3B | thinking on: 1.0, 0.95, 20, `min_p` 0, penalty 1.5. Thinking off: 0.7, 0.8, 20, `min_p` 0, penalty 1.5 | 1.0, 0.95, 20 | the card's thinking-on values, except the engine's `min_p` and no penalty |
   | Qwen3.5-4B, Qwen3.5-9B | the two sets of Qwen3.6-35B-A3B | nothing | the engine's defaults |
   | Qwen3.5-0.8B, Qwen3.5-2B | thinking off, text: 1.0, 1.0, 20, `min_p` 0, penalty 2.0. Thinking on, text: 1.0, 0.95, 20, `min_p` 0, penalty 1.5 | nothing | the engine's defaults |

   The engine's defaults are 0.8, 0.95 and 40, `min_p` 0.05 and no presence penalty, on both engine
   builds the stack runs (`llama-server --help`). On the files measured before the mount moved,
   `/props` read 1.0, 0.95, 64 and `min_p` 0.05 on the gemma pick, 1.0, 0.95, 20 and 0.05 on every
   Qwen deep candidate, and the engine's defaults on the cortex alternate
   ([deep candidates](../readings/deep-candidates.md),
   [pick sampler](../readings/injection-over-pixels-pick-sampler.md),
   [cortex alternate](../readings/injection-over-pixels-alt.md)). On the files the mount holds now
   the header is read and `/props` is not
   ([R-1238](../refinements/tasks/1238-the-lineups-readings-were-drawn-on-files-the-mount-no-longer-holds.md)).
   The Qwen3.5-4B, Qwen3.5-9B and Qwen3.6 cards give a third set, for reasoning with thinking off,
   in two places with different values; it is left out.

5. **Beyond the sampler, what the cards say.**

   | Setting | The cards |
   |---|---|
   | Drafter, gemma-4 | Start the server with `--spec-type draft-mtp --spec-draft-n-max 4`. The default drafter is a `Q4_0` file at the top of the repository, which an engine finds without `--model-draft` when it fetches the model by repository name. The `Q8_0`, `F16` and `BF16` drafters are named with `--model-draft`. |
   | Drafter, Qwen3.5 and Qwen3.6-35B-A3B | The layer is in the model file. Start the server on one slot with `--spec-type draft-mtp` and `--spec-draft-n-max 6`, or 2 for Qwen3.6-35B-A3B. More than one slot and `--mmproj` are not supported with it. |
   | Drafter, Qwen3.8 | The Qwen3.8-27B card names no engine flag. The Flash-Next card states a rate of 1.3 to 1.7 times with its drafter and names no flag. |
   | Flash attention | On for every entry whose card shows an engine command, except gemma-4-E4B, which its card starts with it off. |
   | Image token budget, gemma-4 | 70, 140, 280, 560 or 1120: lower for captions and video, higher for small text. |
   | Thinking | gemma-4: on when the system prompt starts with the template's thinking token. Qwen3.5-0.8B and 2B: off by default. Every other Qwen entry: on by default. Qwen3.8 reads `reasoning_effort` at `xhigh`, `medium` or `low`, and keeps earlier thoughts unless `preserve_thinking` is off. |
   | Context, Qwen3.5-4B, 9B and Qwen3.6 | At least 128K tokens, which the cards say thinking needs. |
   | Embedder input | Each string starts with a task prefix. The card shows `search_query: `. |

6. **Where a tier differs from its card today.**

   | Difference | The card | The stack | Kept or open |
   |---|---|---|---|
   | Sampler of the Qwen3.5 entries, the cortex alternate and the roster alternate among them | the values of decision 4 | the engine's defaults | open, [R-1240](../refinements/tasks/1240-some-tiers-run-settings-their-model-cards-do-not-recommend.md) |
   | `min_p` on every Qwen entry | 0 | 0.05, the engine's default | open, R-1240 |
   | Presence penalty on Qwen3.5 and Qwen3.6 | 1.5 with thinking on, 1.5 to 2.0 with it off | none | open, R-1240 |
   | Flash attention | on, and off for gemma-4-E4B | unset, the engine's `auto` | open, R-1240 |
   | Draft length of the gemma entries | 4 | 3 on every tier | kept: decision 7 |
   | Drafter file of the gemma entries | the `Q4_0` file | the `Q8_0` file | kept: the mount holds the `Q8_0` file and every row was drawn with it |
   | Drafter inside a Qwen file | `--spec-type draft-mtp` with no drafter file | the same once a tier's drafter setting names the tier's own file; no Qwen file drafts unless named | kept: decision 7 |
   | `reasoning_effort` and `preserve_thinking` on Qwen3.8 | settings the template reads | the deep reply sends `medium` unless `CORTEX_REASONING_EFFORT_BRAIN` names another level or is empty, the preserve flag never | the effort kept: [ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md) decision 20; the flag open, [R-1276](../refinements/tasks/1276-the-deep-tier-never-sends-the-templates-preserve-flag.md) |
   | Embedder prefix | on every string | none | open, [R-1241](../refinements/tasks/1241-the-embedder-is-sent-no-task-prefix.md) |
   | Image token budget | one of the five listed | 1024 | kept: chosen on this machine's readings ([ADR-0029](ADR-0029-vision-screen-capture.md)) |
   | Context of a Qwen3.5 or Qwen3.6 tier | at least 128K | 16384 on the cortex and deep tiers, 8192 on a subagent server | kept: the VRAM budget of ADR-0004 decision 11 |

7. **The cortex and each GPU subagent server start with the drafter beside their file, at the
   draft length read fastest on this card.** `drafters.py` in the model manager lists the drafter
   the mount holds beside a lineup file: `mtp-gemma-4-12B-it-Q8_0.gguf` for the cortex pick and
   `mtp-gemma-4-E4B-it-Q8_0.gguf` for the subagent pick. `CORTEX_MODEL_FILE_CORTEX_DRAFT` and
   `CORTEX_MODEL_FILE_SUBAGENT_GPU_DRAFT` name another. Unset, a tier takes the drafter listed for
   its file, and a file with no entry gets none. Empty, the tier starts without one. The default
   follows the file and is not a compose default, so a deployment that names another model does
   not start it with a gemma drafter. The deep tier's drafter stays a named file only
   ([ADR-0004](ADR-0004-model-lineup.md) decision 14).

   The draft length is a setting for each tier, `CORTEX_DRAFT_LENGTH`,
   `CORTEX_DRAFT_LENGTH_SUBAGENT_GPU` and `CORTEX_DRAFT_LENGTH_BRAIN`, each 3, written as
   `--spec-draft-n-max` after the drafter and its type. At the cortex's 16K context a length of 3
   wrote at 1.76 times the no-draft rate, against 1.73 at 2 and 1.61 at 4, the length the gemma
   cards recommend. At the subagent's 8K it wrote at 1.60 times, and 4 to 6 were slower
   ([readings](../readings/tier-drafters.md)). The deep tier's 3 is the engine's own default, which
   gemma-4-31B's rows were drawn at. At 16 bits the pick's Q4 file wrote fastest at 5 at 16K and 20K
   and at 3 at 24K, where 4 is over the card's budget ([readings](../readings/nvfp4-deep-tier.md)),
   so 3 is the longest length that fits at every context the layer fits at. At `q8_0`, the tier's
   default, 3 is also that file's fastest length at 16K ([readings](../readings/kv-cache-types.md));
   a deployment of it at `f16` at 16K or 20K sets 5.

   A GPU subagent server of more than one slot is given a drafter only when its file is listed.
   Every listed file is a gemma file, whose card names no slot limit, and the subagent pick was
   read drafting on two slots. For any other file the model host starts the servers without the
   drafter and logs a warning at boot, since the Qwen cards say multi-token prediction supports
   one slot (decision 5). Leaving the drafter out costs rate only, where refusing the
   configuration would stop a slot shape that ran before the setting existed.

   A tier drafts with the layer inside its own model file when its drafter setting names that
   file. `drafter_flags` then writes `--spec-type draft-mtp` and the draft length with no
   `--model-draft`, so the model is not loaded a second time. The Qwen3.8-27B Q4 file wrote at
   1.75 times its no-draft rate that way at 24K and a draft length of 3. A Qwen entry has no
   listed drafter, so none drafts unless named: Qwen3.5-2B and Qwen3.5-0.8B wrote slower with
   drafting at every context drawn. The cortex drafts with its projector loaded, where a turn
   with a picture answered and most drafted tokens were accepted.

   The CPU subagent servers start without a drafter. `llama-subagent` and `llama-subagent-qwen`
   are compose services whose commands name no `--model-draft`. On the CPU image, with the
   service's four threads and two slots, the gemma-4-E4B drafter at a length of 3 wrote at 1.18
   times the no-draft rate for one request alone and at 0.97 of it with two at once, for
   201 MiB more memory. On one slot with a filled 8K context it wrote at 1.09 times at a length
   of 3 and slower at every other length, and both Qwen files wrote slower at every length
   ([readings](../readings/tier-drafters.md#the-cpu-subagent-server)). The second slot is there
   so that two subagents run at once, which is the case the drafter slows. A compose command
   also cannot leave a flag out when its variable is empty, so a drafter there would need an
   entry script before a deployment could turn it off.

8. **Each tier has a KV cache type setting. The deep tier's default is `q8_0` and every other tier's
   is the engine's 16 bits.** `CORTEX_KV_CACHE_TYPE`, `CORTEX_KV_CACHE_TYPE_BRAIN` and
   `CORTEX_KV_CACHE_TYPE_SUBAGENT_GPU` take `f16` or `q8_0`, the two types the readings have rows
   for, and any other value is refused when the settings are read. At `f16` a tier names no flag. At
   `q8_0`, `cache_flags` in `tiers.py` writes `--cache-type-k q8_0 --cache-type-v q8_0`, and
   `--cache-type-k-draft q8_0 --cache-type-v-draft q8_0` after them when the tier drafts: a tier
   sets one type for the whole server, as the rows did.

   The defaults follow the rule the readings wrote before their rows
   ([KV cache types](../readings/kv-cache-types.md)): the engine accepts the type, the tier gains
   a step of context or 250 MiB, the rate stays at 0.90 of the 16-bit rate or more, and the
   output check passes. A ratio divides two rows of one night where both were drawn
   ([every model](../readings/kv-cache-every-model.md)). No file of the cortex or of a subagent
   server meets it, so those tiers stay at `f16`. Qwen3.8-Flash-Next, a deep candidate split
   between the card, RAM and disk and no tier's file, meets it as written: 0.93 to 0.98 of its
   16-bit rate, with 272 and 424 MiB less on the card in two cells and 155 and 434 more in two,
   as the fit leaves it ([readings](../readings/kv-cache-flash-next.md)). No default follows.

   The deep tier meets it on both files [ADR-0004](ADR-0004-model-lineup.md) names for it, so
   its default is `q8_0`: in `config.py`, and as the substitution default of
   `docker/docker-compose.gpu.yml`, which `crosscheck.py` compares with it.

   - **The pick's file, Qwen3.8-27B in Q4.** It writes 0.92 of its 16-bit rate at 20K and
     takes 570 MiB less there. The model host started the deep tier on it at 16K at `q8_0`,
     drafting with the file's own layer at a draft length of 3: it answered, 1,406 of 1,812
     drafted tokens were accepted, and the card read 16,991 MiB above its floor at the peak.
   - **The alternate's file, gemma-4-31B in Q4.** The model host started it as the stack does,
     at 16K with every layer on the card, at both types, twice
     ([the deep tier at both types](../readings/kv-cache-deep-whole.md)). At 8 bits it writes
     0.913 and 0.912 of its 16-bit rate without a drafter and 1.035 and 1.018 at draft length 3,
     reads 358 to 1,068 MiB less at its highest, and gives the fixed prompt the same reply token
     for token. The smallest margin is the rate without a drafter, 0.912 against 0.90. Started
     on compose defaults, the server's argv names `q8_0` for the model and the drafter, and the
     engine's log at level 4 names `K (q8_0)` and `V (q8_0)` for the caches of both.

   The tier ships with no file named, so the default applies to whichever file a deployment
   names. A deployment on either Q4 file keeps it. A deployment that names an NVFP4 file sets
   `CORTEX_KV_CACHE_TYPE_BRAIN=f16`: the NVFP4 file of Qwen3.8-27B writes 0.81 of its 16-bit
   rate at 32K at 8 bits, and the NVFP4 file of gemma-4-31B has no row held whole. The default
   follows the files ADR-0004 names, so a choice in
   [R-1244](../refinements/tasks/1244-the-deep-tiers-file-is-not-chosen-between-the-q4-and-the-nvfp4-files.md)
   that moves the pick to an NVFP4 file moves the default back to `f16`.

   The drafter's cache keeps the model's type. The draft layer inside a Qwen file takes more
   memory with its cache at 8 bits than at 16, 82 to 86 MiB on the pick's file at 48K
   ([R-1263](../refinements/tasks/1263-a-qwen-tier-at-q8-0-gives-its-draft-layer-a-cache-that-takes-more-memory.md)).
   That changes nothing for the pick: its rows were drawn with the drafter's cache at 8
   bits, so the 570 MiB is what is left after that cost.

   The pick's file is inside the model budget at 16K at both types: 16,995 MiB at `q8_0` and
   17,465 MiB at `f16` at draft length 3 ([readings](../readings/kv-cache-types.md)). The
   default does not make the alternate fit it. At 16K with every layer on the card the
   alternate's file is over the 18,177 MiB at both types: by 198 to 207 MiB at `q8_0` without
   the drafter and 907 to 909 MiB with it, and by 1,266 and 1,597 MiB at `f16`. 8 bits takes
   less, and what a deployment of that file gets at 16K is decided in
   [R-1264](../refinements/tasks/1264-gemma-4-31b-at-16k-is-over-the-model-budget-with-every-layer-on-the-card.md).

   The engine exits on an 8-bit V cache when flash attention is off. The stack cannot start a
   server that way: no tier's argv names a flash attention flag, which a test of the roster
   asserts with every tier at `q8_0`, so each server runs the engine's `auto`, and `auto` turns
   flash attention on for an 8-bit cache (read on gemma-4-E4B and on both Q4 deep files).

## Consequences

- The three picks run their cards' temperature, `top_p` and `top_k` with no setting in this repo,
  because their files contain them. Another publisher's file of the same weights may contain none,
  so a change of a pick's file is also a change of sampler until its header is read.
- "At the engine's sampler" names one sampler for a gemma entry and another for a Qwen3.5 entry.
  Rows of two entries are compared with that difference in view.
- A card is its publisher's text and can change at any time. This record describes the cards as
  they read on the day its Context names.
- A header is read without loading the model, so what a file sets is checked before a draw, and
  `/props` on the loaded file confirms it.
- A drafter is memory on the card: about 515 MiB on the cortex at 16K and 112 MiB on a subagent
  server at 8K. The cortex reservation of [ADR-0012](ADR-0012-resource-governance.md) decision 14
  is 8.9 GiB, which covers the cortex with its projector and its drafter, and the subagent request
  of 3.5 GiB covers a server with its drafter.
- A change of a tier's default file is also a change of its drafter: the new file needs an entry
  in `drafters.py`, or the tier stops drafting.

## Alternatives rejected

- **Setting each card's sampler as a server flag now**: for the picks it would change only `min_p`,
  which the gemma cards do not name, and for the Qwen3.5 entries no row exists at the card's values.
- **Keeping the card values only in backlog tasks**: a task closes and is no longer read, and the
  values are the reference for every later pick.
- **A compose default for a drafter file**: `${VAR:-default}` cannot be turned off by an empty
  value, and it would pass a gemma drafter to whatever model a deployment names.
- **Refusing a drafter on a server of several slots**: see decision 7.
- **`f16` as the deep tier's default because the tier ships with no file**: both files the
  lineup names for the tier meet the rule, so the default would suit neither, and a deployment
  on an NVFP4 file sets one variable.
- **Every cache type the engine accepts**: no row exists for a type under 8 bits.
- **A flash attention setting checked against the cache type**: the stack has no such setting.
  [R-1240](../refinements/tasks/1240-some-tiers-run-settings-their-model-cards-do-not-recommend.md)
  decides whether a tier gets one, and a tier that does refuses `off` beside `q8_0`.
- **A readings record for the card values**: a readings record holds a measurement taken here with
  its method. A card is a recommendation, and the decision is how far the tiers follow it.

## Related

- [ADR-0004](ADR-0004-model-lineup.md), [ADR-0029](ADR-0029-vision-screen-capture.md),
  [ADR-0041](ADR-0041-injection-image-variant.md),
  [ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md),
  [ADR-0060](ADR-0060-injection-rows-follow-the-tier.md).
- Readings: [deep candidates](../readings/deep-candidates.md),
  [pick sampler](../readings/injection-over-pixels-pick-sampler.md),
  [cortex alternate](../readings/injection-over-pixels-alt.md),
  [thinking switch](../readings/thinking-switch.md), [tier drafters](../readings/tier-drafters.md),
  [KV cache types](../readings/kv-cache-types.md),
  [the deep tier at both cache types](../readings/kv-cache-deep-whole.md),
  [KV cache on every model](../readings/kv-cache-every-model.md).
