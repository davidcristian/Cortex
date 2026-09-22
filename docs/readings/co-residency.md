# Readings: two tiers on one card

What the tiers cost on the 24 GB card, what a spill does to decode rate, and what llama.cpp's
`timings` object reports. Cited by [ADR-0030](../adr/ADR-0030-brain-handoff.md) (the context's tier
sizes) and [ADR-0055](../adr/ADR-0055-co-residency-and-spill-watch.md). The procedure is the
co-residency section of the [model-swap](../runbooks/model-swap.md) runbook.

## What each pairing costs, and how a spill shows

**2026-08-07**, RTX 5090 Laptop reporting 24463 MiB, driven through the shipped `model-host` control
API with the real tiers. VRAM is `nvidia-smi` total used minus the idle baseline, which moved
between 1529 and 2836 MiB inside one session because the desktop shares the card; decode is
llama.cpp's own `timings.predicted_per_second`, so request overhead is excluded. These are absolute
because a reader compares them against their own card to decide whether a pair fits.

| Resident | Above the baseline | Deep decode |
| --- | --- | --- |
| cortex alone (gemma-4-12B QAT q4_0, 16K, projector, 1024-token image budget) | 8448 to 8468 MiB | |
| deep alone (gemma-4-31B QAT q4_0, 8K, `-ngl 99`) | 19117 to 19125 MiB | 25.07 to 33.28 tok/s |
| cortex, then deep | wanted 29139 MiB of 24463 | 14.80 to 17.29 tok/s |
| deep and the gemma-4-E4B subagent tier (8K, `--parallel 2`) | peer 2878 MiB, 908 MiB left free | 28.92 to 29.82 tok/s |

The overcommitted pair **loaded**: both tiers reported `ready` and 496 MiB read free, the same
reading as the genuine fit, while the deep model decoded at about half its solo rate and its first
prefill after each switch fell to about a tenth of its solo rate. The cortex, loaded first, kept its
solo rate. Generating on the fitting pair at once cost both some rate and allocated nothing (23639
MiB under load against 23642 idle), so a spawn onto a resident tier is not a VRAM decision. The
cortex's peak, which its reservation must cover, was 8573 MiB, the vision path adding 70 to 90 MiB
([ADR-0012](../adr/ADR-0012-resource-governance.md)). Method: start and stop tiers through the
control API, read `nvidia-smi` and one completion's `timings` per variant.

## What the spill watch reports on the card

**2026-08-08**, same card, through the shipped `LlamaCppBackend` and `CadenceWatch`, three
completions of about 120 words per variant, judged against a declared 25.0 tok/s threshold:

| Variant | Card afterwards | Best decode | Result |
| --- | --- | --- | --- |
| deep alone, cold onto a clear card | 2310 MiB free | 33.78 tok/s | not collapsed |
| cortex resident, then deep | 423 MiB free | 22.77 tok/s | collapsed |
| deep alone after the peer was evicted under it | 8649 MiB free | 29.82 tok/s | not collapsed |

Every resident tier reported `ready` in every variant. The spilled deep tier did not fully recover
when its peer left (88% of its cold rate, with more card free than the cold load had), so the
threshold is set from a cold load. Loading the cortex second instead cost the deep model less (a
best of 23.28 tok/s against 20.32 the other way), the driver paging the newcomer first. Method: the
middle and last variants are `packages/inference/tests/test_decode_cadence_live.py`,
integration-marked; the cold variant was driven from a script through the same adapter and has no
committed reproducer.

## What the `timings` object contains

**2026-09-15**, `ghcr.io/ggml-org/llama.cpp:server` build `b10680-d7bd3bfca`, a 0.8B model on CPU:
the final chunk of a streaming `/v1/chat/completions` contains one `timings` object with
`predicted_per_second` beside `prompt_n`, `prompt_ms`, `prompt_per_second` and `cache_n`, and no
earlier chunk contains one (the same held for build `b10298-15586e2d7` on 2026-08-08). `prompt_n`
counts only tokens not served from cache: asked the same question twice, the cold request reported
`cache_n` 0 and `prompt_n` 21, the repeats `cache_n` 17 and `prompt_n` 4, also with `--cache-ram 0`.
So a mostly cached prompt reads slower: the repeats' prompt rate was 0.37 to 0.39 of the cold one on
one server and one prompt. The streaming fixture `_TIMINGS` in
`packages/inference/tests/test_cadence_contract.py` has the same fields. Method: two identical
requests against one server, reading the last chunk.

## A drafter-sized overcommit, and the E4B pair on the current image

**2026-09-22**, same card, `server-cuda` at `sha256:952424b09abc` (`b10680`), driver 616.92, bare
`llama-server` containers running the tiers' shipped argv, the deep tier started second as a
handoff starts it and the E4B tier idle beside it. Each start served one reasoning prompt (thinking
on, `max_tokens` 512) and the `search_email` tool-call turn, one warm-up and three timed requests
each, seed 42. Memory is absolute; rates are ratios of the same deep configuration alone. Free is
total minus used; `memory.free`, the figure the fit check reads, is 326 MiB lower, the driver's
`memory.reserved`.

| Memory reading | MiB |
| --- | --- |
| deep tier alone at ready, above the idle floor | 19117 plain, 20118 to 20142 drafting |
| E4B tier alone at ready, idle, above the idle floor | 3294 to 3307 |
| free before a drafting deep load beside the E4B tier | 19201, so 917 to 941 short |
| free before a plain deep load beside it, two starts | 19866 and 19874, so 749 and 757 spare |
| free at ready in each of those three starts | 910 to 952 |

| Start | Reasoning decode | Tool-call decode | SM clock over max |
| --- | --- | --- | --- |
| drafting beside E4B, of drafting alone | 0.79 | 0.80 | 0.62 to 0.64 against 0.47 to 0.49 |
| plain beside E4B, of plain alone, first start | 0.36 | 0.36 | 0.86 against 0.56 to 0.57 |
| plain beside E4B, of plain alone, second start | 0.63 | 0.62 | 0.76 to 0.77 against 0.56 to 0.57 |

Clocks were not matched: in every pair the slower start ran the higher clock, at 0.91 to 1.03
times the median power of the start it is compared with. The drafting starts accepted the same drafts per
request (299 of 632 on the reasoning prompt, 90 of 285 on the tool call), so their difference is the
card's. Against the slowest healthy drafting completion, a tool call and the highest floor these
readings allow without a false alarm, the overcommitted tool call's best rate was 0.82 of it and the
overcommitted reasoning trace's best 1.02. The overcommitted drafting tool call decoded 1.02 times
the plain tier's own tool-call median alone. Alone, the drafting tier decoded 1.62 times the plain
tier on this reasoning prompt and 1.27 times on the tool call, at the clocks above. The idle floor
fell by 664 MiB at some point during the drafting overcommitted start, read only once its
containers were gone, so its shortage while the turns ran was between 253 and 941 MiB. The E4B
pair that read as a fit on 2026-08-07 at 908 MiB free spilled in both starts here. Method:
`measurements/drafter-spill-2026-09-22/` (`draw.py`, `draw_plain.py`, the registration written
before each draw), `nvidia-smi` sampled every 2 s.

## Why the E4B pair read as a fit in August

**2026-09-22**, same card and driver: the E4B tier alone on each build with the argv it had then,
`nvidia-smi` read idle and 5 s after ready, then E4B tiers started one after another on `b10680`
until they passed the card.

| Reading | MiB |
| --- | --- |
| E4B tier on `server-cuda-b10236` (`sha256:fd68d1301314`), the 2026-08-07 argv, above idle | 3286 |
| E4B tier on `b10680`, the current argv, above idle | 3293 |
| llama.cpp's own buffers on both builds: model 2696.06, KV 208, compute 106.02 | 3010 |
| each of six stacked E4B tiers, above the one before | 3297 to 3310 |
| `memory.free` after the seventh and the eighth, 246 and about 3550 MiB past the card | 277 and 301 |

Neither the engine nor the argv grew the tier: the two flags added since August, `--reasoning-budget
0` and `--cache-ram 0`, allocate nothing on the device. The 2878 MiB recorded on 2026-08-07 is less
than the tier's own buffers, so that day either part of the pair was already off the card or the
idle floor moved between the two readings it was subtracted from; the 908 MiB that pair left free
is the level every spilled start above reached. That level is not a reserve the driver keeps: the
stacked tiers took `memory.free` to 277 MiB. Beside the peer the deep tier added 18931 and 18922
MiB to the card against its 19117 alone, so part of it went to system memory although `memory.free`
before the load, 19541 and 19549 MiB, was over 400 MiB above its cost; how much it holds above that
cost while it loads is unread. Method: `measurements/e4b-cost-2026-09-22/` (`stack.sh`, the two
servers' `-v` logs and their `nvidia-smi` readings).
