# The drafter's cache type

A tier at `q8_0` that drafts gives its drafter the model's type: `cache_flags` in
`brain/packages/model_manager/src/cortex_model_manager/tiers.py` adds `--cache-type-k-draft q8_0
--cache-type-v-draft q8_0`. These readings say what that type does to card memory for the two
kinds of drafter the lineup has. Memory figures only; the rates beside them are those of
[the remaining cells](kv-cache-remaining-cells.md#the-chat-models-the-models-cache-and-the-drafters-cache)
and [every model](kv-cache-every-model.md), drawn on 2026-11-20 and 2026-11-21.

## A gemma drafter keeps no cache of its own

The drafter files of gemma-4-12B, gemma-4-E4B and gemma-4-31B each have four layers, and on build
`b12375` the engine logs `llama_kv_cache: layer N: sharing with layer M` for all four: the
drafter reads the cache of the model's last two layers and holds none of its own. So its cache type sets
nothing, which is why gemma-4-12B read the same memory to 8 MiB and the same rate at both drafter
types at 64K and 128K. Method: the model host's log of any launch with one of these drafters,
for example `logs/cores/host.log` of `~/.cache/cortex-run/2026-11-23/s4/`.

## A Qwen draft layer: the cache saves less than the compute buffer grows

A Qwen file drafts with one layer inside it, which has a cache of its own. At 8 bits that cache
is about half its 16-bit size, and the engine reserves a larger compute buffer for the draft
context. Each pair below is two launches on one date, build `b12375`, with only the drafter's
type changed and the model's cache at `q8_0`. The buffer columns come from launches at `-lv 4`.

| file | context | draft cache, 16 and 8 bits | draft compute buffer, 16 and 8 bits | card at load with the 16-bit drafter cache |
| --- | --- | --- | --- | --- |
| Qwen3.8-27B Q4, the deep pick | 16K | 64 and 34 MiB | 148.02 and 160.02 MiB | 16 MiB more |
| Qwen3.8-27B, Q4 and NVFP4 files | 48K | not read | not read | 82 to 86 MiB less |
| Qwen3.5-9B | 64K | not read | not read | 150 MiB less |
| Qwen3.5-9B | 128K | 512 and 272 MiB | 172.02 and 696.02 MiB | 282 MiB less, and 286 and 292 |

- **The sign changes with the context.** At 16K the 8-bit type saves 30 MiB of cache and costs 12
  of compute, so at 8 bits the drafter takes 18 MiB less by the engine's buffers and 16 less on
  the card. At 128K it saves 240 and costs 524. For the 27B the 16-bit type starts to take less
  at a context between 16K and 48K, which no row has.
- **The model's own buffers do not move.** At 16K both launches read model 15104.40, cache 544,
  recurrent state 598.50 and compute 180.02 MiB; at 128K cache 2176, recurrent state 201 and
  compute 704.02 MiB. The exit breakdown counts only the model's context, so it puts the
  difference in `unaccounted`: 2076 and 2362 MiB at 128K.
- **The rate stays inside the spread of a row**: 0.99 to 1.01 for the 27B at 48K, and 1.004,
  0.955 and 1.036 for Qwen3.5-9B, 16-bit drafter cache over 8-bit.

The 16K pair, 2026-11-24: the card's floor read 2236 MiB after each launch and 2244 and 2236
before, and the pair is the model host's deep argv for the pick (`-ngl 99 --ctx-size 16384
--parallel 1 --jinja --cache-ram 0`, `q8_0` for the model's cache) with `--spec-type draft-mtp
--spec-draft-n-max 3`, the drafter's type and `--fit off -lv 4`. The model host on compose
defaults, with both `CORTEX_MODEL_FILE_BRAIN` and `CORTEX_MODEL_FILE_BRAIN_DRAFT` naming the
pick's file, wrote that argv with the four cache flags at `q8_0` and read 16,965 MiB above the
floor at load, as the 8-bit launch did. The reasoning effort is a request field
(`CORTEX_REASONING_EFFORT_BRAIN`, medium by default) and is not in the argv. Method: `bare.sh`
and `mh.sh` of `~/.cache/cortex-run/2026-11-24/s2/`, the logs in `logs/` beside them. The 128K
pair of 2026-11-23 read 9141 and 9423 MiB above the floor: `r1263.sh` of
`~/.cache/cortex-run/2026-11-23/s4/`, its server logs `logs/r1263-f16.server.log` and
`logs/r1263-q8_0.server.log` beside it. The other rows: the records linked above.
