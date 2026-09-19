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
