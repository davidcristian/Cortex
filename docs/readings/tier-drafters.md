# Readings: the cortex and subagent tier drafters

Rate and memory rows for the multi-token-prediction drafters the cortex tier and the GPU subagent
tier start with by default, a live check of the default stack with them, and the row that
leaves the CPU subagent server without one.
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

## The default stack through tool turns, a handoff and filled contexts

**2026-11-18**, the same build and files, with the brain built from the tree over the base, gpu,
memory, tools and subagents compose files: the cortex with its projector, both GPU subagent
servers, and the deep tier `unsloth/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_M.gguf` with
`CORTEX_ESCALATION` on and both server ids in `CORTEX_SWAP_EVICT_MODELS`. A recording proxy
between the brain and the cortex kept every request and reply.

- **Tool turns.** Seven turns went to the stack with the drafters and to the same stack with both
  drafter settings empty: a fact to store, a question that recalls it, a reminder, a request to
  forget, a picture of three bands, about 500 words, and one delegated spawn whose subagent lists
  a directory with its tool. Both stacks made the same tool calls with the same outcomes
  (`schedule_task`, `forget_memories` after its card, `spawn_subagents`), every cortex request
  ended in `stop` or `tool_calls`, no reply was cut, and the engine logged no error. With the
  drafters the engine accepted 0.62 to 0.90 of the drafted tokens on the six requests that ended
  in a tool call, and the subagent's own tool call ran on a GPU server.
- **A store request.** `Remember that my bike lock code is 4417.`, memory emptied before each
  turn, on one brain and one tool list. The rule was written before the draw: a difference of 2
  turns of 12 or fewer is no difference. The turn's first request ended in a tool call nobody
  asked for in 3 of 12 turns with the cortex drafter and in 2 of 12 with
  `CORTEX_MODEL_FILE_CORTEX_DRAFT` empty. The typed check refused each call, and all 24 turns
  stored the fact.
- **A handoff.** One chat stated a fact, asked for the deep tier, and asked for the fact again.
  The model host read the cortex and both subagent servers `stopped` with the card at 2,425 MiB,
  the deep tier alone peaked at 18,835 MiB, and afterwards the three servers read `ready` and the
  chat answered with its fact. In a second run one chat had a batch of two spawns in flight when
  another chat asked for the handoff: the stops came after the batch ended, the fit check read
  21,723 MiB free against the 16,200 MiB declared, both chats finished, and each answered with
  its own fact. The log does not show whether the drain waited or the batch ended first.
- **A server that stops.** The first subagent server was killed while both servers were writing
  a batch of two spawns. The killed spawn logged
  `a GPU-placed subagent did not answer; re-running it once on the CPU` and finished there, the
  other spawn finished on its server, the recheck pass started the killed server again, and the
  next delegated spawn ran on the GPU with no warning. A spawn asked for in the turn right after a
  handoff, while the servers still read `loading`, ran on the CPU.
- **One server stopped.** With `subagent-gpu` stopped through the control API and
  `subagent-gpu-2` serving, three lone spawns out of three ran on the second server and none on
  the CPU server, and so did one spawn delegated in a chat turn. Of a batch of two spawns in that
  state one ran on the second server and the other on the CPU, with the stopped server's address
  in the warning. Log: `~/.cache/cortex-run/2026-11-18/slot9/logs/live.txt`, and `live2.txt` for
  the lone spawns a second time.
- **Filled contexts.** With the three servers loaded the card read 17,598 to 17,617 MiB. With a
  request of 7,597 prompt tokens on each subagent server and one of 15,736 on the cortex at once,
  it peaked at 17,638 to 17,646 MiB: about 15,220 MiB above the card with every tier stopped, and
  1,160 MiB under the cap. One filled subagent request alone raised the card by 14 MiB. The
  highest reading of the seven turns was 17,672 MiB.
- **`q8_0`.** With `CORTEX_KV_CACHE_TYPE` and `CORTEX_KV_CACHE_TYPE_SUBAGENT_GPU` set to `q8_0`
  the three servers started, each drafted on a text request, the card read 17,156 MiB loaded, and
  the second handoff above ran on that stack.
- **Escalation off.** With `CORTEX_ESCALATION` unset and no start sent through the control API,
  the model host started the cortex and both subagent servers at boot, the three read `ready`
  and the card read 17,689 MiB. A batch of two spawns ran one on each server and none on the CPU
  server, in two draws out of two, and the card peaked at 17,719 and 17,726 MiB while the cortex
  wrote. After the second server's process was killed the model host started it again at its
  first attempt. Logs: `live.txt` and `live2.txt` in
  `~/.cache/cortex-run/2026-11-18/slot9/logs/`.
- **A cold boot under escalation.** With the deep tier named and both ids in the evict list, the
  model host started the three servers, the brain's boot recovery sent `start` to each subagent
  server and stopped none, its log had no warning, and the card read 17,676 MiB. In a handoff
  drawn with the same settings the cortex and both subagent servers were stopped, the deep tier
  peaked at 18,914 MiB, the model host started none of the stopped servers by itself, and the
  three read `ready` again afterwards. Logs: `bootcheck.txt`, `handoff.txt` and `watch-h.txt` in
  `~/.cache/cortex-run/2026-11-18/slot9/logs/`.

Method: `up.sh`, `turns.sh`, `nodraft.sh`, `stepc.sh`, `stepd.sh`, `stepk.sh`, `stepm.sh`,
`escoff.sh`, `fill.py` and `count.py` in `~/.cache/cortex-run/2026-11-18/slot8/`, compose project
`cortexn24`, logs in `logs/` there and the proxy's record in `proxy/log/requests.jsonl`.

## The CPU subagent server

**2026-11-18**, the subagent file on the CPU image `ghcr.io/ggml-org/llama.cpp:server`, build
b10680, which is older than the model host's b12375. The server ran with the compose service's
flags on `--cpuset-cpus 12-15`: `-ngl 0 --cpus 4.0 --threads 4 --parallel 2 --ctx-size 8192`
under 8g, without a drafter and with the subagent drafter at a draft length of 3. The rule was
written before the row: no drafter unless one request alone and each of two at once both write
at 1.1 times the no-draft rate or more. A rate is a ratio of the median of one request alone
without the drafter, on a 20-token prompt with 256 tokens written. A busy cell is the range of
six requests, two at once in three rounds. Memory is the cgroup's peak, which counts the mapped
model file.

| row | one alone | each of two at once | cgroup peak | drafted tokens accepted |
| --- | --- | --- | --- | --- |
| no drafter | 1.0 | 0.67 to 0.69 | 6,960 MiB | none drafted |
| drafter at 3 | 1.18 | 0.64 to 0.67 | 7,161 MiB | 0.22 to 0.27 of them |

One request alone gained 0.18. With both slots busy the median request wrote at 0.97 of the
no-draft median, so the row fails the rule on two requests at once, the case the server's
second slot is for. The drafter cost 201 MiB. The model baseline of 2026-11-16 read the same
file on the same image with four CPUs, one slot and a filled 8K context
(`measurements/model-baseline-2026-11-16/baseline.md`): 1.09 times the no-draft rate at a draft
length of 3, and under it at 1, 2, 4 and 5, down to about 0.7 at 5. Qwen3.5-2B and Qwen3.5-0.8B
wrote at about 0.8 of their no-draft rates at a length of 1 and slower at 2 and 3. Method:
`cpudraw7.sh slots slots-draft` and `cpudrive7.py` in `~/.cache/cortex-run/2026-11-18/`, logs
`logs/cpu2-slots.txt` and `cpu2-slots-draft.txt`.
