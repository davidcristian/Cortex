# The engine's prompt cache may grow to the whole memory cap of the container it runs in

**Status:** done 2026-09-13
**Area:** resource-governance
**Origin:** [ADR-0059](../../adr/ADR-0059-prompt-cache-per-tier.md)

The five-pick envelope measurement ran each subagent pick on a container with the subagent compose
file's three cgroup caps, and the kernel killed the `Qwen3.5-4B` server with exit 137 and an `oom`
event 174 seconds into its first subtask shape, after 67 completions. The `gemma-4-E4B` server
before it had read `memory.peak` at exactly the cap, 8589934592 bytes, and the `Qwen3.5-2B` server
8279199744, while every layer of each was on the card, so what filled the cap was host memory the
engine keeps for itself. Drawn again without the memory cap, the same 4B server peaked at
12387135488 bytes, 11.5 GiB, over the same 288 replies, and all 67 cells the killed run had finished
matched the redraw exactly in output and tokens.

**What that host memory is.** `llama-server` at `b10680-d7bd3bfca`, on both the `server` and the
`server-cuda` tags, keeps a prompt cache in host RAM whose size `--cache-ram` sets, and its help
reads `default: 8192`. That is 8 GiB, the same number as the `mem_limit` and `memswap_limit` the
subagent compose file and its roster twin put on each CPU server from
`CORTEX_SUBAGENTS_MEM_BUDGET_GB`. No compose file and no model-host argv in this repo passes
`--cache-ram` or `LLAMA_ARG_CACHE_RAM`. The model-host sidecar's 24 GiB cap covers three tiers, each
a child server with the same 8 GiB default.

**What the shipped CPU server does,** measured 2026-09-13. The default pick on the `server` tag was
started with the compose file's own argv (`-ngl 0`, `--ctx-size 8192`, `--parallel 2`,
`--threads 4`) in a container with the same three caps. It sat at `memory.current` 7411 MiB of the
8192 MiB cap the moment it finished loading and before it served a request: 4930 MiB of mapped model
file, that artifact being 5154941280 bytes on disk, and 2451 MiB of anonymous memory for the KV
cache and the compute buffers. That leaves 781 MiB. Twelve distinct prompts of about 850 tokens were
then sent one at a time, and anonymous memory rose on every one, by 144 MiB on the first and by 55
to 105 MiB after that. On the tenth prompt, 8536 prompt tokens in, `memory.peak` read the cap
exactly, and the mapped model file started falling instead, 4931 to 4869 to 4814 to 4746 MiB over
the next three prompts, while anonymous memory went on rising to 3412 MiB.

So the cache never gets near its own 8192 MiB ceiling on this server, because the model's memory is
counted first and the cache has 781 MiB to spend. The worse half is that spending it takes nine
prompts, and what pays for the tenth onward is evicting the weights this same container reads on
every token. On the card, where the weights are in VRAM and no reclaimable page cache stands in for
them, the kernel takes the process instead.

**The flag is the setting, at no measured cost on this shape.** The same server started with
`--cache-ram 0` loaded at 2452 MiB of anonymous memory, one MiB from the other run, so the cache is
not preallocated. Over the same twelve prompts and the same 10240 prompt tokens its anonymous memory
rose by 144 MiB on the first and by 67 MiB in total over the eleven after it, ending at 2663 MiB
against the other run's 3412, with `memory.current` at 7609 MiB against the other's 8192 and the
mapped model file never reclaimed. Prompt eval ran at 76 to 80 tokens per second in both and the
twelfth prompt finished at 135.3 seconds against 135.2. This is the worst case for the flag, every
prompt being distinct; a delegated batch reusing a system prefix is where the cache could pay.

**What the GPU tier does,** measured 2026-09-13 on the subagent pick at `-ngl 99` under the model
host's own 24 GiB cap, on the shape the cache exists for: four conversations of about 1100 prompt
tokens rotating through two server slots, four rounds each, at temperature 0 and a fixed seed. The
default spent 100 MiB of host memory per cached conversation and answered a returning conversation
in 0.11 to 0.19 s. With `--cache-ram 0` memory held flat from the fourth request on and answers took
0.24 to 0.29 s, 7.77 s against 6.59 s over the sixteen requests. All sixteen cells returned the same
completion either way, so the cache changes what a request costs and not what it answers. It does
pay on this shape, and what it pays with is up to 8192 MiB of a cap that also holds another tier's
mapped weights.

**What closed it.** `--cache-ram 0` on every subagent server this repo starts, the two CPU compose
servers and the model host's hosted subagent tier, required by a fourth rule in
`scripts/flagcheck.py`, which derives that set from the stack's own wiring and argv and so reaches
both placements and any server a later override adds. The value is zero rather than a size because
the CPU containers have 781 MiB of headroom to give a cache and the tier's subtasks are one-shot.
The cortex and the deep tier keep the engine's default: they are the tiers a cache is most likely to
pay on, and this reading does not transfer to them.

## History

- 2026-09-11: opened by the five-pick envelope measurement. The `docker events` record reads `oom`
  then `die` with exit 137 for the container at 05:43:37; the server log and the aborted samples are
  kept in the session's scratch directory under `five-pick-retable-4b-oom/`.
- 2026-09-13: checked and corrected. The flag, its 8192 MiB default and its environment variable
  were read back off `--help` on the `server` tag at `b10680-d7bd3bfca`, and no compose file or
  model-host argv passes either. The opening claim that the cache "may reach the container's whole
  cap before the model's own memory is counted" is wrong on the shipped CPU server and is replaced
  by the reading above. The CPU measurement this entry had recorded as missing was taken, and so was
  the effect of `--cache-ram 0` on it. Both are under `measurements/cache-ram-2026-09-13/`, which
  git ignores.
- 2026-09-13: done. The GPU measurement answers both questions that were open on that tier: the
  cache costs 100 MiB per cached conversation and saves 0.13 s on a request that returns to a taken
  slot, and a seeded pair returns the same sixteen cells, so the flag changes cost and not output.
  The flag is now on both compose servers and the hosted tier, and the check that requires it fails
  when either shipped server loses it or changes it, proven by two mutations in its own suite
  (`scripts/tests/test_flagcheck.py`). The cortex and deep tiers are left on the engine's default.
