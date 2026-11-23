# Readings: the tiers the model host starts at boot

What the model host did with the tiers it starts at boot, the cortex and each GPU subagent server:
a server killed at every load, and the line it logs about the card's free memory once every boot
tier answers ready. The decisions these rest on are in
[ADR-0054](../adr/ADR-0054-baseline-residency.md) decision 9.

## A server that keeps exiting

Taken on 2026-11-18 on the 24 GB card: the default stack with escalation on, both GPU subagent
servers in the evict list, and the model host from the `cortex-model-host` image (engine build
`b12375`) with the tree's packages bound over it.

- **Killed at every load.** With all three servers `ready`, the second subagent server's
  `llama-server` was killed with `kill -9` each time it started. The model host loaded it 4
  times, logged `a model process exited without being asked to; starting it again` 3 times and
  `a model process keeps exiting, so it is left stopped` once, and `GET /models/subagent-gpu-2`
  then answered `failed` with the `start_gap` `the process of 'subagent-gpu-2' exited 4 times in
  a row, the last with code -9, so it is left stopped until a stop is asked for or the model host
  starts again`. The cortex and the first server answered `ready` throughout.
- **Two recheck intervals later.** The brain had logged 3 lines that name the server, once each:
  the adapter's `a hosted model process has failed`, the pass's `a tier of the baseline residency
  stopped without anything asking it to`, and `the model host names a reason it will not start
  this tier`. The model host had received 1 `start` for that server in the whole run, the one of
  the brain's boot recovery, and had loaded it 4 times in all.
- **A cortex context that fills the card.** With `CORTEX_CTX_SIZE=49152` the card read 18,390 of
  24,463 MiB with all three `ready`. With 400000 it read 23,324 MiB (the engine's log gives the
  cortex's slot a context of 262144), all three answered `ready` and no server exited, so on this
  card a larger context alone gives the bound nothing to do
  ([R-1255](../refinements/tasks/1255-nothing-checks-that-the-tiers-the-model-host-starts-at-boot-fit-the-card.md)).

Method: `fit.sh` and `fit2.sh` in `~/.cache/cortex-run/2026-11-18/slot12/`, logs `logs/fit.txt`
and `logs/fit2.txt`.

## The boot fit line

Taken on 2026-11-23 on the 24 GB card: the model host alone, from the `cortex-model-host` image
(engine build `b12375`) with the tree's model manager and core bound over it, on compose defaults
except for the settings named below. The launches ran in the order default, short, default, and
other apps held 1,699, 1,698 and 1,580 MiB of the card before each.
The line is written by `BootFit` in
[boot_fit.py](../../brain/packages/model_manager/src/cortex_model_manager/boot_fit.py), and the
free figure it logs was compared with the `memory.free` that `nvidia-smi` read on the host in
the same second.

| Boot roster | Free in the line | `nvidia-smi` free | Line |
| --- | --- | --- | --- |
| compose defaults: the cortex alone, `--ctx-size 16384`, two launches | 14,373 and 14,483 MiB | 14,373 and 14,483 MiB | `INFO`, once |
| `CORTEX_CTX_SIZE=400000`, the cortex's F32 projector, two gemma-4-E4B GPU subagent servers at 8192 | 890 MiB | 890 MiB | `WARNING`, once |

```text
INFO:cortex_model_manager.boot_fit:the tiers started at boot leave the card its free floor contexts=cortex=16384 floor_mib=1536 free_mib=14373 total_mib=24463
WARNING:cortex_model_manager.boot_fit:the tiers started at boot leave the card less free memory than its floor contexts="cortex=400000 subagent-gpu=8192 subagent-gpu-2=8192" floor_mib=1536 free_mib=890 total_mib=24463
```

- **The argv.** The cortex ran `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf` with `-ngl 99 --parallel 1
  --cache-ram 8192`, no cache type flag, no reasoning budget flag, and the drafter
  `mtp-gemma-4-12B-it-Q8_0.gguf` at `--spec-draft-n-max 3`; the short roster added `--mmproj`,
  `--image-max-tokens 1024` and `--ubatch-size 1024`. Each subagent server ran
  `gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf` at `--ctx-size 8192`, `--reasoning-budget 0`,
  `--cache-ram 0` and its own MTP drafter.
- **The short roster.** All three servers answered `ready` and none exited. The engine's log names
  a context of 400128 and caps the cortex's slot at 262144, the model's training context. After
  the project was removed the card read 1,586 MiB used, 112 MiB below the reading before it.

Method: `launch.sh A fit` and `launch.sh B short` in `~/.cache/cortex-run/2026-11-23/s6/`, with
the rules written first in `notes.md` there; logs in `logs/A/`, `logs/A2/` and `logs/B/`.
