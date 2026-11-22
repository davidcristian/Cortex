# The deep tier's first request after a load

What the first request to a newly loaded deep server takes beyond a later request of the same
size, and where that time goes. It continues
[the deep turn of a handoff](nvfp4-deep-pair.md#the-deep-turn-of-a-handoff), whose rows first
read a fixed time there. The larger part of it is a compile, and the stack keeps what the
compile writes in [a named volume](#a-volume-for-the-compiled-kernels).

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
record's first handoff was a first load.

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

## A volume for the compiled kernels

**2026-11-22**, the same card, file, argv and requests, on the `cortex-model-host` image as it
was built, with no image build. `docker/docker-compose.gpu.yml` mounts the named volume
`compute-cache` at `/var/tmp` on `model-host` and sets `CUDA_CACHE_PATH=/var/tmp/ComputeCache`
in its environment. The library reads that variable for its directory, and the model host
starts each engine process with its own environment. The rule for the change was written before
these rows: nine points, three new containers a cell, against untreated first loads of the
same night.

Ten launches and twelve deep loads, every row at a median power limit of 0.89 of the card's
maximum with no reading under it. The untreated first loads are seven: the five above,
one drawn earlier on that date, and one drawn in turn with these rows, which read 1.005 of the
six's first prompt pass and 1.037 of their load. A kept volume is one an earlier container wrote.
A later pass is the median over the 17 rows above and the 11 the model host started here.

| point | the rule | read | holds |
| --- | --- | --- | --- |
| 1. the first token | a new container's first deep load on a kept volume, three of them: first prompt pass 1.6 later passes or less; the client's first token 0.40 or less of an untreated first load's | 1.41 (1.39 to 1.47); 0.286 (0.281 to 0.298) | yes |
| 2. the whole deep turn | the load, the first token and 1,000 tokens written under 1 of the untreated turn by the medians | 0.981 (0.966 to 0.988) | yes |
| 3. what must not change | the load within 0.10; the highest reading above the floor within 16 MiB of the untreated rows' 16,993 to 17,003 MiB; the first request's write rate within 0.05; both timeouts as they were | 1.022 (1.004 to 1.035); 16,993 in all three MiB; 1.010; the change names neither `CORTEX_SWAP_LOAD_TIMEOUT_S` nor `CORTEX_INFERENCE_STALL_TIMEOUT_S` | yes |
| 4. an empty volume | three new volumes: each first container's first prompt pass and load within 0.10 of the untreated medians, and the files in the volume afterwards, owned by uid 10001 | first prompt pass 1.012, 1.004 and 1.005; load 0.999, 1.017 and 1.022; each volume 39 files and 51 MB, all owned by uid 10001, 20 MB of it after the cortex tier's load | yes |
| 5. a later load in the same container | on an empty volume and on a kept one: a fixed time of 0.25 or less of an untreated first load's | 0.103 on the empty volume and 0.101 on the kept one | yes |
| 6. an image that has the library's own directory | the same mount on an image with `/home/cortex/.nv` made by its user passes point 1 | one container: first prompt pass 1.45 later passes; first token 0.294; nothing written under `/home/cortex/.nv` | yes, on one container |
| 7. a volume that is empty and owned by root | the first container that mounts it at `/var/tmp` writes it | one container: the volume was empty and owned by root with mode 755, took mode 1777 at the mount, and had the 39 files after, owned by uid 10001; first prompt pass 0.977 and load 1.025 of the untreated medians | yes |
| 8. another engine build on a kept volume | it starts and answers; its first prompt pass is no longer than the same build's with no volume, and its load no longer than the same build's started the same way with no volume | build b12169 answered both requests; first prompt pass 0.93 of its own with no volume; load 0.99 | yes |
| 9. the scans and the runbook | `volumecheck.py` and `bindcheck.py` pass; the runbook says what the volume has in it and that `down -v` removes it | both pass; [llamacpp-gpu.md](../runbooks/llamacpp-gpu.md#teardown) | yes |

**A later load reads the volume as it reads a container's own layer.** The second deep load of
the container on a new volume had 0.105 of its first load's fixed time, and a container with no
volume reads 0.07 to 0.10 there.

**Why the target is `/var/tmp`.** A new named volume takes the owner and mode of the image
directory it is mounted over, and is owned by root with mode 755 where the image has none. The
image has `/var/tmp`, empty and owned by root with mode 1777, so the image's user, uid 10001,
can write a volume mounted there and the image needs no directory made for it. It has no
`/home/cortex/.nv`, where the library writes when the variable is unset. Two launches mounted a
volume there: each started and answered, the volume stayed empty and no log line named the
directory, and a second deep load in one container had 0.98 of the first load's fixed time, so
the library, with nowhere to write, compiled on every deep load. The volume holds whatever a
process writes to `/var/tmp`. After a deep load that was the library's directory and nothing
else.

**Another engine build reads part of these and compiles the rest.** Build b12169, from
`ghcr.io/ggml-org/llama.cpp:server-cuda`, was started by `docker run` as the same uid with the
same argv. With no volume that build wrote 34 files and 43 MB. On the volume the model host's
build had written, with the variable set, it added 17 files and 28 MB beside the 51 MB, and
its first prompt pass read 0.93 of its own with no volume. Two earlier launches of it, on such
a volume mounted for that build at the library's own directory, read 0.93 and then, with its
own files there, 0.28. Its load, timed from `docker run` with no container yet, read 0.99 of
the same build's started the same way with no volume, and 0.98 and 0.97 in the two earlier
launches. So a rebuild that moves the engine build pays most of the compile once more, and the
older build's files stay in the volume until `down -v` removes it.

## What these rows do not say

- Anything about the NVFP4 file. Its first and later loads in one container are in
  [the deep turn of a handoff](nvfp4-deep-pair.md#the-deep-turn-of-a-handoff): it compiles
  kernels of its own after this file's, and its later loads have 0.07 of its first load's
  fixed time. No row drew it with the volume.
- What the cortex and subagent tiers pay on their first request in a new container. The one
  cortex request above has no later request to divide it by.
- What a cache written under another driver does. The library names each file by a hash, and
  every launch here ran on one driver.
- What the model host's build reads on the volume after another build wrote into it. Every
  kept row was drawn before the other build's launch.
- An image built from `brain/Dockerfile.modelhost` on that date. None was built: a build takes
  the `server-cuda` base the registry has on that day, so it can change the engine build under
  every tier. Point 6's image is the image as built with one `mkdir` run in it and stored as a
  layer.
- What `--no-warmup` or the library's `CUDA_MODULE_LOADING=EAGER` do to the smaller time.
  Neither was drawn.
- Anything at another prompt size. The pair record read the first load's fixed time the same
  at 896 and at 10,856 prompt tokens. The smaller time of its later loads read 0.64 as large
  at 10,856 tokens as at 896 for this file and 0.86 for the NVFP4 file, three loads a cell.

Method, under `measurements/model-baseline-2026-11-16/`: `nvfp4-probes/firstfixed.py` starts
the model host once (compose project `cortexn27`) and starts and stops the deep tier through it
for every load of the launch; `nvfp4-probes/fixedread.py` reads the groups. Rows in
`bench/first-fixed-2026-11-22.jsonl` (17 rows, all kept), the three first loads of the pair
record in `bench/pair-first-2026-11-22.jsonl`. `nvfp4-probes/k2vol.py` draws the volume's
launches from the compose file as it is and `nvfp4-probes/k2read.py` reads them against the
nine points, rows in `bench/kernel-vartmp-2026-11-22.jsonl` (12 rows, all kept).
`bench/kernel-volume-2026-11-22.jsonl` has the sixth untreated load, the other build's launch
with no volume and its two earlier ones, and one launch of a volume mounted where the image has
no directory; `bench/kernel-nobuild-2026-11-22.jsonl` has the other, with two deep loads in its
one container. The rule for each step was written in `nvfp4-probes/notes-2026-11-22.md` before
its launch, and the engine's log and the container's file list are in the run directory beside
the compose files.
