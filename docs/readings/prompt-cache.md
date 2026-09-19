# Prompt cache

What `llama-server`'s host-RAM prompt cache (`--cache-ram`) costs and buys on each tier, read for
[ADR-0059](../adr/ADR-0059-prompt-cache-per-tier.md). "Anon" is the container's anonymous memory,
"mapped" the model file mapped into it, both from the cgroup's `memory.stat`. Every variant pair ran
at temperature 0 and a fixed seed on `ghcr.io/ggml-org/llama.cpp:server-cuda` at
`sha256:952424b09abc` (`b10680-d7bd3bfca`), whose default cache size is 8192 MiB. Method: the
scratch drivers under `measurements/cache-ram-2026-09-13/` and
`measurements/cache-ram-tiers-2026-09-13/`, which git ignores.

## The kill that opened it

**2026-09-11.** A `Qwen3.5-4B` Q4_K_M server at `-ngl 99` under the subagent compose file's 8 GiB
memory cap was killed 174 seconds into an envelope measurement, exit 137 with an `oom` event, after
67 completions. Without the memory cap and with the CPU cap and thread count kept, all 67 finished
cells paired identically with the redraw. The gemma-4-E4B server of the same measurement peaked at
the cap without being killed.

## The subagent tier

**2026-09-13**, the shipped CPU pick (gemma-4-E4B QAT q4_0) with the subagent compose file's argv
and its three cgroup caps, twelve distinct prompts of about 850 tokens each:

| variant | anon at load | anon after 10240 prompt tokens | mapped model file | `memory.current` | twelfth prompt at |
| --- | --- | --- | --- | --- | --- |
| engine default | 2451 MiB | 3412 MiB | 4931 falling to 4746 MiB | held at the 8192 MiB cap | 135.2 s |
| `--cache-ram 0` | 2452 MiB | 2663 MiB | 4916 MiB, never reclaimed | 7609 MiB | 135.3 s |

The default variant held 7411 MiB of the 8192 MiB cap once loaded, before any request, which left
781 MiB for the cache. Nine prompts used that up, and from the tenth on the kernel reclaimed mapped
weights. Prompt evaluation ran at the same rate in both variants.

The same pick on the card at `-ngl 99` under the model host's 24 GiB cap, four conversations of
about 1100 prompt tokens rotating through two slots, four rounds each: the default variant spent
about 100 MiB of host memory per cached conversation and answered a returning conversation in 0.11
to 0.19 s; the `--cache-ram 0` variant held flat and answered in 0.24 to 0.29 s, 7.77 s against 6.59
s over sixteen requests. Both variants returned the same completion on all sixteen cells.

## The cortex and the deep tier

**2026-09-13**, each tier's own argv from the model host's `config.py`, a container with the model
host's 24 GiB cap and the models mount, three conversations of 4018 prompt tokens rotating through
the tier's one slot, four rounds each.

`gemma-4-12B` (cortex) at `-ngl 99` and a 16384-token context:

| variant | anon at load | anon after twelve requests | mapped model file | `memory.current` | a returning request | twelve requests in |
| --- | --- | --- | --- | --- | --- | --- |
| engine default | 332 MiB | 4099 MiB | 6836 MiB, never reclaimed | 10967 MiB | 1.42 to 1.78 s | 29.4 s |
| `--cache-ram 0` | 332 MiB | 1404 MiB | 6836 MiB, never reclaimed | 8266 MiB | 3.44 to 3.61 s | 44.3 s |

A cached conversation cost 1349 MiB. Two were cached at any moment and every return was restored.
The first round cost 4.2 to 4.4 s in both variants. The variants returned the same trace on ten of
twelve cells, and the same prompt drew different traces between rounds inside each variant.

`gemma-4-31B` (deep) at `-ngl 99` and an 8192-token context, 16991 MiB of mapped weights:

| variant | anon at load | anon after twelve requests | mapped model file | `memory.peak` | a request | twelve requests in |
| --- | --- | --- | --- | --- | --- | --- |
| engine default | 338 MiB | 9910 MiB | 17014 falling to 14585 MiB | held at the 24576 MiB cap | 10.5 to 11.3 s | 129.9 s |
| `--cache-ram 0` | 338 MiB | 2859 MiB | 17025 MiB, never reclaimed | 19953 MiB | 9.1 to 10.0 s | 113.5 s |

A cached conversation cost 3526 MiB; no request in the default variant was restored. All twelve
cells matched between the variants. Alongside the cortex's 8192 MiB cache limit the GPU subagent
tier loads at 5440 MiB with no cache, a worst case of 20.8 GiB of the 24 GiB cap.
