# Readings: the cortex and subagent tier drafters

Rate and memory rows for the multi-token-prediction drafters the cortex tier and the GPU subagent
tier start with by default, and a live check of the default stack with them.
[ADR-0077](../adr/ADR-0077-model-card-settings.md) decision 7 is the decision these rows support.
Memory is `nvidia-smi` `memory.used` less what the card held before the load, and stays absolute
because a reader compares it with their own card. A rate describes only the card it was read on,
so each one is written as a ratio of the no-draft rate of the same file at the same context.

| name here | file under the models mount |
| --- | --- |
| cortex file | `unsloth/gemma-4-12B-it-qat-GGUF/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf` |
| cortex drafter | `unsloth/gemma-4-12B-it-qat-GGUF/mtp-gemma-4-12B-it-Q8_0.gguf` |
| subagent file | `unsloth/gemma-4-E4B-it-qat-GGUF/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf` |
| subagent drafter | `unsloth/gemma-4-E4B-it-qat-GGUF/mtp-gemma-4-E4B-it-Q8_0.gguf` |

Every row is from **2026-11-18** on `llama-server` build b12375 from the `cortex-model-host`
image, on the 24 GB card (24,463 MiB), unless it names the model baseline of 2026-11-16.

## The cortex file at its default context

The baseline drew the cortex file from 64K up, and the tier runs at 16K by default. These rows
decide the tier's default draft length. The rule was fixed before the draw: the default is the
length with the highest rate, and the drafter is a default only if that rate is at least 1.10
times the no-draft rate.

One server at a time, started with `--ctx-size 16384 --parallel 1 --jinja --cache-ram 0 -fa on
-ngl 99 --fit off`, the gemma card's sampler and the default 16-bit cache. A drafting launch adds
`--model-draft`, `--spec-type draft-mtp` and `--spec-draft-n-max`. The rate is read while 256
tokens are written after a prompt that fills the context less 512 tokens, as the median of three
seeds. A launch is kept when `enforced.power.limit` over `power.max_limit` has a median of 0.84 or
more across it, the rule the baseline keeps a row on. The other launches read 0.80 to 0.83.

| draft length | kept launch, times the no-draft rate | every launch | drafted tokens accepted | at load | at the peak |
| --- | --- | --- | --- | --- | --- |
| none | 1.00 | 0.98 to 1.00, 4 launches | | 7,553 MiB | 7,567 to 7,571 MiB |
| 1 | no launch was kept | 1.46 to 1.49, 4 launches | 341 of 423 | 8,067 MiB | 8,083 MiB |
| 2 | 1.73 | 1.66 to 1.73, 4 launches | 439 of 646 | 8,067 MiB | 8,082 to 8,083 MiB |
| 3 | 1.76 | 1.74 to 1.78, 4 launches | 489 of 821 | 8,067 MiB | 8,081 to 8,084 MiB |
| 4 | 1.61 | 1.55 to 1.61, 3 launches | 493 of 1,081 | 8,067 MiB | 8,083 to 8,085 MiB |
| 5 | 1.50 | 1 launch | 506 of 1,284 | 8,067 MiB | 8,085 MiB |

Every ratio is against the kept no-draft launch. A length of 3 is the fastest: its slowest launch
is above the fastest launch at 2, and it was above 2 in each of the four passes. A length of 4,
which the gemma cards recommend, drafts more tokens than 3 and has about as many accepted, so it
writes slower. The drafter adds about 515 MiB at load and at the peak.

Method: `tools/tier-drafters.py gemma-4-12B 16384 cortex-16k 7250 0,1,2,3,4,5` under
`measurements/model-baseline-2026-11-16/`, which git ignores, then the same command with
`0,1,2,3 1` for a second pass of the lengths with no kept launch. It calls the baseline driver
`tools/bench3.py`. Rows are in `bench/tier-drafters.jsonl` there.

## The subagent file at its default context

The baseline drew the subagent file at 8K, the tier's default
(`measurements/model-baseline-2026-11-16/baseline.md`, 2026-11-16 and 2026-11-17, the method
above with `-fa off`). A length of 3 wrote at 1.60 times the no-draft rate, and 4 to 6 were slower
than 3. At 128K a length of 2 was the fastest. On two slots of one server at 8K the drafter at a
length of 3 wrote at 1.45 times the no-draft rate with one slot busy
([subagent budget](subagent-budget.md#two-slots-against-two-servers)).

Two files have no default drafter on these rows. Qwen3.5-2B and Qwen3.5-0.8B wrote slower with
drafting at every context drawn. Qwen3.5-9B was fastest at a length of 4 at 64K (1.46 times) and
Qwen3.5-4B at 3, and their layer is in the model file, which no setting drafts with.

## The default stack on the card

The model host was started from the compose files with only `CORTEX_MODEL_FILE_SUBAGENT_GPU` set,
to the subagent file. It listed `cortex`, `subagent-gpu` and `subagent-gpu-2`, and the engine
logged `loading draft model` once for each of the three with the drafter of its file.

| what was asked | result |
| --- | --- |
| one text request to the cortex | 180 of 357 drafted tokens accepted |
| one text request to each subagent server | 58 of 309 drafted tokens accepted on each |
| two spawns through the brain's own wiring on a 16 GB cap, an 8.6 GiB reservation and a 3.5 GiB request, while the cortex wrote 500 tokens | `placed_at_once` 2, both subagent servers busy in 75 of 158 samples, the cortex busy in each of those, no server with more than one slot busy |
| the engine's log | a `draft acceptance` line for each request, for example `draft acceptance = 0.50420 (  180 accepted /   357 generated)` |

Memory above the floor read just before each load:

| loaded | at load | at the peak |
| --- | --- | --- |
| the cortex and two subagent servers, each with its drafter | 14,418 MiB | 14,446 MiB |
| the cortex with its projector and its drafter | 8,808 MiB | 8,868 MiB |
| one subagent server with its drafter | 3,180 MiB | 3,186 MiB |
| one subagent server, `CORTEX_MODEL_FILE_SUBAGENT_GPU_DRAFT` set empty | 3,068 MiB | 3,074 MiB |
| one subagent server of two 8K slots with its drafter | 3,367 MiB | 3,371 MiB |

The three servers at their peak are 1,938 MiB under the 16,384 MiB of the 16 GB soft cap, when the
card read 16,874 MiB of its 24,463 in use. The cortex with its projector and its drafter peaks 62 MiB
over the 8,806 MiB of an 8.6 GiB reservation, so the reservation is 8.9 GiB: 9,114 MiB, 246 MiB over
that peak. With it the placer still places two 3.5 GiB requests under the cap, a charge of 15.9 GiB. One subagent server with its drafter is 398 MiB under
the 3,584 MiB of its 3.5 GiB request, and the drafter is 112 MiB of it. The one-server rows were
read from a floor taken after the cortex, which the host starts at boot, had stopped; the rows of
the same shape in [subagent budget](subagent-budget.md#two-slots-against-two-servers) read about
255 MiB higher
([R-1246](../refinements/tasks/1246-the-one-model-subagent-rows-read-higher-than-a-paired-reading.md)).

The cortex with `CORTEX_MODEL_FILE_CORTEX_MMPROJ` set to `mmproj-F32.gguf` of its folder drafts
with the projector loaded. A turn with a 96 by 96 picture of one colour named the colour in its
thought, with 1,070 of 1,286 drafted tokens accepted. A turn with a 2,048 by 1,152 picture of
three bands, 1,045 prompt tokens, answered "The colors in this image are red, green, and blue",
with 615 of 753 accepted. The peak was 8,866 MiB with the first picture and 8,868 MiB with the
second.

One server of two slots (`CORTEX_SUBAGENTS_GPU_SERVERS=1`, `CORTEX_SUBAGENTS_GPU_PARALLEL=2`, a 16K
pool) kept the drafter in its argv, the host logged no warning, and two requests sent at once
both drafted: 70 of 270 drafted tokens accepted on one slot and 65 of 282 on the other.

With `CORTEX_MODEL_FILE_CORTEX_DRAFT` set empty the cortex's argv ended at `--cache-ram 8192`, and
with the subagent setting empty the server's replies had no draft counts.

Method: `shape3.sh <label> [projector|big|subagent|plain|slots]` and `ask3.py` in
`~/.cache/cortex-run/2026-11-18/`, compose project `cortexn24`, the model host from the existing
image with the working tree's model manager bound over it, logs `logs/drafters*.txt` there.
