# Model lineup

The measurements the per-tier picks of [ADR-0004](../adr/ADR-0004-model-lineup.md) rest on. VRAM is
`nvidia-smi` total used on a card reporting 24463 MiB unless a row says "above the baseline", which
subtracts the same card read with nothing loaded; a total includes whatever the desktop held, so
compare candidates within one table and not across tables. Injection counts are in [injection text
rows](injection-text-rows.md), and what each entry's template renders for the thinking switch is in
[thinking switch](thinking-switch.md) (the lineup's switched tails).

## Cortex

**2026-06-29**, llama.cpp `server-cuda` of that date, 16K context, one slot, every layer on the
card:

| candidate | weights only | with projector |
| --- | --- | --- |
| Qwen3.5-9B Q4_K_M | 9.2 GB | 11.0 GB (F32 projector, +1.8) |
| gemma-4-12B q4_0 QAT | 11.0 GB | 11.3 GB (projector 0.18 GB, +0.3) |

**2026-08-07**, build of that date, through the model host at the tier's shipped shape (`-ngl 99
--ctx-size 16384 --parallel 1 --jinja`, projector, `--image-max-tokens 1024`): the cortex costs 8400
to 8484 MiB idle and 8573 MiB at its peak above the baseline, 9832 MiB as a total. The 2026-06-29
rows are another build's. Method: the model host's control API and `nvidia-smi` read before the load
and after the last measurement.

## Deep candidates

**2026-08-04**, build `b10236-1464c62d8`, each candidate alone on the card through the model host
with the cortex stopped, `-ngl 99`, 8192 context, one slot, the baseline 1867 to 1932 MiB.
"Answered" counts four escalation-grade questions answered inside a 4096-token budget; rates are
ratios of the pick's.

| candidate | artifact | model alone | decode | answered |
| --- | --- | --- | --- | --- |
| gemma-4-31B q4_0 QAT (pick) | 17.65 GB | 19128 MiB | 1.0 | 4 of 4 |
| Qwen3.6-27B Q4_K_M (alternate) | 16.82 GB | 16443 MiB | 0.97 | 3 of 4 |
| Qwen3.6-35B-A3B UD-Q3_K_M | 16.60 GB | 15995 MiB | 2.6 | 1 of 4 |
| gemma-4-26B-A4B q4_0 QAT | 14.44 GB | 14607 MiB | 2.6 | 0 of 4 |

With no cap at the shipped 8192 context, both mixture-of-experts candidates spent 8057 to 8092
tokens and returned an empty reply on both questions asked; the pick answered in 4448 and 3847
tokens and the alternate in 3104 and 3340, both ending on end-of-generation. At a 16384 context the
pick costs 658 MiB more. The four cold loads read the mount at 142 to 177 MB/s; a bare cold load of
the pick used about a third of `CORTEX_SWAP_LOAD_TIMEOUT_S`'s 300 s, and a second load with the file
partly in page cache took two thirds of the first. Method: `CORTEX_MODEL_FILE_BRAIN` and
`CORTEX_CTX_SIZE_BRAIN` changed between runs, the questions posted by hand, `n_predict` read off
`/props`.

## Subagent pick against the one it replaced

**2026-07-03**, the subagent compose server on the CPU (`-ngl 0 --jinja`, thinking off, 8192
context, two slots), ratios of the old pick:

| | Qwen3.5-2B Q4_K_M (replaced) | gemma-4-E4B QAT q4_0 (pick) |
| --- | --- | --- |
| weights | 1.19 GB | 4.9 GB |
| load off the mount | 1.0 | 2.6 |
| resident memory after inference | 1.0 (about 893 MiB) | 2.8 |
| a narrow task ("17 + 25") | 1.0 | 3.0 |
| tool call with `--jinja` | works | works |

## Embedder

**2026-06-29**, nomic-embed-text-v1.5 Q8_0 on a CPU `llama-server`: 0.146 GB of weights, about 18
MiB resident, a real embedding streamed back deterministically, 768 dimensions. Method: the
`cortex_embedding` integration suite against the live sidecar.

## The CPU subagent server

**Thread count, 2026-09-11**, the pick's CPU server under `--cpus 4.0 --memory 8g --memory-swap 8g`
on `server` at `sha256:db057ec90de0` (`b10680-d7bd3bfca`), one injection-harness row each: with the
engine's default of 24 threads the row took 13.7 times as long as with `--threads 4`, prompt
evaluation ran at about a tenth and decoding at about a twenty-fifth of the `--threads 4` rates, and
the cgroup was throttled in 14,308 of 14,520 periods. `--threads 4.0` starts 4 threads, `2.5` starts
2, and `0.5` starts the default; a whole `--cpus 0.5` container with `--threads 0.5` started 24.

**Decode per slot with `--threads 4`, 2026-09-11**, the compose stack's own server, a 233-token
report summarized at `max_tokens` 400, ratios of the idle one-slot median; "saturated" is one busy
shell loop per hardware thread on the host:

| host | slots decoding | decode per slot |
| --- | --- | --- |
| idle | 1 | 1.0 (12.24 to 12.44 tok/s) |
| idle | 2 | 0.69 to 0.75 |
| saturated | 1 | 0.40 |
| saturated | 2 | 0.25 |

A capped delegated attempt (1024 tokens, about 100 prompt tokens) took 86.6 to 86.8 s one at a time
and 121.8 to 122.9 s two at once (2026-09-15), so the 2400 s run deadline is about twenty times the
longer on an idle host.

**Memory, 2026-09-08 and 2026-09-15**, the pick's server's own cgroup:

| reading | loaded, one 64-token completion | after three delegated batches |
| --- | --- | --- |
| `memory.current` of the 8 GiB `memory.max` | 90.4% | 93.2% |
| `memory.stat` `anon` | 2.40 GiB | 2.62 GiB |
| `memory.stat` `file` (the mapped artifact) | 4.80 GiB | 4.80 GiB |
| `memory.events` `max`, `oom_kill`; refaulted file pages | 0, 0; 0 | 0, 0; 0 |

`docker stats` read 2.44 GiB for the first, having subtracted `inactive_file`. Under the injection
harness's 1600-token budget over ten attacks per variant, the same server reached the cap in every
run. Method: `cat` of the container's `/sys/fs/cgroup` files; the delegated batches through
`SpawnSubagentsTool` over the shipped runner at the shipped budgets.

## Memory search

**2026-08-11**, pgvector 0.8.4 on PostgreSQL 16.14 (`pgvector/pgvector:pg16`), a synthetic corpus of
768-dimension unit vectors from 256 topic centres (mean pairwise cosine 0.170 against 0.381 for
twenty real sentences through the live embedder), queried through `PgVectorMemoryStore.search` at
the shipped width of 20. Times are ratios of the 0.515 s time to first token of a recalling turn:

| rows | exact search, unfiltered (ships) | scoped to one session |
| --- | --- | --- |
| 1,000 | 0.04 | 0.003 |
| 220,000 | 2.9 | not re-measured |

The cost is per candidate row (k=5 and k=20 cost the same), most of it detoasting each out-of-line
vector and the distance arithmetic. An `hnsw` index (`m=16`, `ef_construction=64`, `ef_search=40`)
answered 268 times faster, took 859 MB against the 688 MB table, and kept on average 0.550 of the
exact top 20 (0.575 of the top 5), the worst query keeping none. `SET STORAGE PLAIN` made the exact
scan 22% faster and the table 34% larger. An `ivfflat` build needed more than the default 64 MB of
`maintenance_work_mem`. A straight line through the two sizes crosses the time to first token at
about 75,000 rows.

## The deep pick's drafter

**2026-09-17**, `server-cuda` at `sha256:952424b09abc`, the deep tier's shipped argv, one warm-up
and four timed requests of a reasoning prompt at `max_tokens` 512, seed 42. The drafter,
`assistant-F16.gguf` (954,843,360 bytes, `gemma4-assistant`), decoded 1.86 and 1.89 times the plain
median against a plain spread of 0.02, accepting 0.60 of its drafts; named without `--spec-type` it
drafted nothing at the plain rate. It cost 997 to 1020 MiB.

**2026-09-19**, a second run with the rule written down first: drafter, plain, drafter, a tool-call
turn (`max_tokens` 1024) and an answer-text turn (thinking off, `max_tokens` 512), a pair counting
when both variants' power limits overlap and the cap is active in most busy samples. Ratios of the
plain median:

| turn | drafter decode | plain spread | accepted | drafter clock over plain |
| --- | --- | --- | --- | --- |
| tool call | 1.34, 1.34 | 0.021 | 270 of 855 | 0.86, 0.84 |
| answer text | 1.34, 1.34 | 0.015 | 618 of 1827 | 0.80, 0.80 |

Both turns met the rule. Every drafting start ran at a lower SM clock than the plain one at the same
power, about 1.17 times the power per unit of clock, which is why a matched-clock rule could not be
met. A drafting start reached ready in 1.09 to 1.17 times the plain start's load, and stood 998 to
1009 MiB above it. Method: `measurements/mtp-2026-09-19-ceiling/` drivers, `nvidia-smi` sampled
every 2 s.
