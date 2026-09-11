# The engine's prompt cache may grow to the whole memory cap of the container it runs in

**Status:** open, actionable
**Area:** resource-governance
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

Opened 2026-09-11 by the close of
[R-640](640-the-five-pick-envelope-table-is-on-an-image-the-stack-no-longer-pulls.md). The
re-table addendum at the origin ran each subagent pick on a container carrying the subagent compose
file's three cgroup caps, and the kernel killed the `Qwen3.5-4B` server with exit 137 and an `oom`
event 174 seconds into its first subtask shape, after 67 completions, with its log ending on the
slot it had just picked for the 68th. The `gemma-4-E4B` server before it had read `memory.peak` at exactly the cap,
8589934592 bytes, and the `Qwen3.5-2B` server 8279199744, while every layer of each was on the
card, so what filled the cap was host memory the engine keeps for itself. Drawn again without the
memory cap, the same 4B server peaked at 12387135488 bytes, 11.5 GiB, over the same 288 runs, and
all 67 cells the killed run had finished paired with the redraw identically in output and tokens.

**What that host memory is.** `llama-server` at `b10680-d7bd3bfca`, on both the `server` and the
`server-cuda` tags, keeps a prompt cache in host RAM whose size `--cache-ram` sets, and its help
reads `default: 8192`. That is 8 GiB, the same number as the `mem_limit` and `memswap_limit` the
subagent compose file and its roster twin put on each CPU server from
`CORTEX_SUBAGENTS_MEM_BUDGET_GB`, so the cache alone may reach the container's whole cap before the
model's own memory is counted. No compose file and no model-host argv in this repo passes
`--cache-ram`. The model-host sidecar's 24 GiB cap covers three tiers, each a child server with the
same 8 GiB default.

**What is not known.** Whether the shipped CPU server reaches the cap under a real delegated load
has not been measured: its weights are mapped from the file, which the kernel can reclaim, where
the cache is the engine's own allocation. The kill above is on the CUDA image with the weights in
VRAM, which is the tighter case for this question only in that nothing else competes.

**What would close it.** A decision on the flag for each capped server: a `--cache-ram` read from
the same variable as the cap less the model's measured footprint, a fixed small size, or `0`, with
the cost of each read off seeded runs, since a prompt-cache hit is the state a seeded completion
reproduces against (the ADR-0005 paired-arms addendum), and then the constant scan holding the flag
to the cap the way it holds `--threads` to the CPU quota.

## Trail

- 2026-09-11: opened by the re-table addendum at the origin. The `docker events` record reads
  `oom` then `die` with exit 137 for the container at 05:43:37; the server log and the aborted
  samples are kept in the session's scratch directory under `five-pick-retable-4b-oom/`.
