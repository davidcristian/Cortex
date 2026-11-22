# The deep tier's first request after a load

What the first request to a newly loaded deep server takes beyond a later request of the same
size, and where that time goes. It continues
[the deep turn of a handoff](nvfp4-deep-pair.md#the-deep-turn-of-a-handoff), whose rows first
read a fixed time there, and
[R-1291](../refinements/tasks/1291-a-new-model-host-container-compiles-the-cards-kernels-again.md)
proposes the change these rows point at. Nothing that ships was changed on them.

## Two fixed times

**2026-11-22**, the 24 GB card beside the desktop's apps, engine build b12375 from the
`cortex-model-host` image. The model host started the deep pick's file,
`unsloth/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_M.gguf`, on compose defaults:
`--ctx-size 16384 --parallel 1 --cache-ram 0`, `q8_0`, the file's own draft layer at
`--spec-draft-n-max 3`. After each load came a first chat request, a system and a user message
of 896 prompt tokens at `reasoning_effort` `medium` that wrote 300 tokens, and then a second of
the same size with another text, so none of its prompt was cached. Every load was a new server
process that read the file through the models mount: the page cache held about 2 GB before each
start, and the 17 loads are 0.06 apart.

The unit below is a **later pass**: the second request's prompt pass over its 896 tokens, the
median of all 17 rows, which are 0.12 apart at most. Every row has a median power limit
of 0.89 of the card's maximum and no reading under it.

The first prompt pass after a load is longer than a later pass by a fixed time. That time has
two sizes, and the container decides which, not the load:

| the deep load is | loads | first prompt pass, in later passes | of that, over a later pass |
| --- | --- | --- | --- |
| the first of a new model host container | 5 | 4.94 | 3.87 (each 3.84 to 4.04) |
| a later load in the same container | 2 | 1.38 | 0.39 (0.38 and 0.39) |

The five first loads are the three of the pair record and two of these launches. A later load
has 0.10 of a first load's fixed time. So a stack pays the larger time once, on the first
handoff after it starts, and every later handoff pays the smaller one. Every row of the pair
record was a first load.

## What the larger time is

The card's library compiles the engine's kernels on their first use and keeps the result in a
cache directory inside the container. Three things say so.

- **The engine's log.** One first load ran with the log at its verbose level and stamps
  (`LLAMA_ARG_LOG_VERBOSITY=4`). Its first pass read 5.08 later passes, so the log did not hide
  the time. Of what that pass had over the second request's, 0.86 was inside the first decode
  call of the prompt, the 231 tokens of the system message: between `sched_reserve: reserve
  took` and `cached n_tokens = 231` the engine writes no line. Another 0.11 was between
  `created context checkpoint 3 of 32` and the first token, and 0.03 in the three checkpoint
  writes. The steps between were level with the second request's. The engine's own warm-up,
  `warming up the model with an empty run`, runs at load, before `creating MTP draft context`,
  and the first request pays the time after it.
- **The container's files.** After a first load's two requests, the only files the container
  had changed since its start, beside four under `/etc`, were 51 MB of `.bin` files under
  `/home/cortex/.nv/ComputeCache/`. That directory is in the container's writable layer, so a
  new container starts without it and a later server process in the same container reads it.
- **The directory kept.** With a host directory bound at `/home/cortex/.nv`, the first
  container wrote it and read as any first load, 4.94 later passes. The next three new
  containers started with what it wrote, and each one's first deep load read 1.37
  (1.33 to 1.38): the fixed time of a later load, 0.09 of a first load's. Nothing was added
  to the load, which read 1.01 of the untreated first loads'. The larger time is removed,
  not moved.

**A request to the cortex tier first does not take it.** In a running stack the cortex answers
before any handoff. One launch sent the cortex tier a request of 934 prompt tokens before
stopping it. The deep tier's first pass then read 4.33 later passes, with 0.84 of a first
load's fixed time left. So a request to the cortex tier takes 0.16 of it at most, and the first
handoff of a stack pays the rest. That is one row.

## The draft layer

Without the draft layer (`CORTEX_MODEL_FILE_BRAIN_DRAFT` empty, so the argv ends at
`--cache-type-k q8_0 --cache-type-v q8_0`):

| the deep load is | loads | fixed time, over the same load's with the draft layer |
| --- | --- | --- |
| the first of a new container | 3 | 0.99 |
| a later load in the same container | 2 | 0.67 |

The larger time is not the draft layer's. A third of the smaller one is: a server process
without the layer has 0.13 of a later pass less to do before its first token.

## A request before the tier is used

The smaller time is paid by every new server process, so a cache does not take it. Three later
loads sent a request that writes one token on a prompt of 21 tokens before the timed one.

| reading, in later passes | untreated later load | with the request before |
| --- | --- | --- |
| the small request, whole | | 0.50 |
| timed first prompt pass | 1.38 | 1.17 |
| of that, over a later pass | 0.39 | 0.18 (each 0.10 to 0.19) |
| small request and timed pass together | 1.38 | 1.67 |

The small request moves the time and adds to it. The timed request's fixed time falls to
0.47 of the untreated one, but the small request takes 1.29 times the whole untreated fixed
time, since it has a pass of its own. A model host that sent it before reporting the tier
ready would bring the first token of a later handoff forward by 0.21 of a later pass and
lengthen the load by 0.50 of one. The whole deep turn would be longer by the difference.

## What these rows do not say

- Anything about the NVFP4 file. Its fixed time on a first load is 2.03 times this file's, and
  no later load of it is drawn
  ([R-1293](../refinements/tasks/1293-the-nvfp4-files-first-request-is-drawn-only-on-a-new-containers-first-load.md)).
- What the cortex and subagent tiers pay on their first request in a new container. The one
  cortex request above has no later request to divide it by.
- What a cache written by another engine build or another driver does. The library names each
  file by a hash, and no launch here read a directory another build wrote.
- What `--no-warmup` or the library's `CUDA_MODULE_LOADING=EAGER` do to the smaller time.
  Neither was drawn.
- Anything at another prompt size. The pair record read the first load's fixed time the same
  at 896 and at 10,856 prompt tokens.

Method, under `measurements/model-baseline-2026-11-16/`: `nvfp4-probes/firstfixed.py` starts
the model host once (compose project `cortexn27`) and starts and stops the deep tier through it
for every load of the launch; `nvfp4-probes/fixedread.py` reads the groups. Rows in
`bench/first-fixed-2026-11-22.jsonl` (17 rows, all kept), the three first loads of the pair
record in `bench/pair-first-2026-11-22.jsonl`. The rule for each step was written in
`nvfp4-probes/notes-2026-11-22.md` before its launch, and the engine's log and the container's
file list are in the run directory beside the compose files.
