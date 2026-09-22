# The roster alternate's CPU server has neither cgroup cap

**Status:** done 2026-09-11
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)

`llama-subagent` in `docker/docker-compose.subagents.yml` is capped at `cpus: 4.0` with `mem_limit`
and `memswap_limit` at 8 GiB, which are the brain's own `DEFAULT_CPU_BUDGET` and
`DEFAULT_MEM_BUDGET_GB` and which `scripts/crosscheck.py` compares against those constants.
`llama-subagent-qwen` in `docker/docker-compose.subagents-roster.yml` is a second CPU llama-server,
layered on top of that file rather than merged into that service, and it declared none of the three.
It got the host's whole CPU and unlimited memory.

This is more than a compose omission. The scheduler charges a roster entry's declared ask,
`cpus: 2.0, memory_gb: 1.5` for this entry, against the same soft budget it charges the default
entry's, so the brain's ledger assumes both servers live inside one budget while nothing on the host
enforced that for the second. The injection harness also draws a CPU row for Qwen3.5-2B, the
artifact this override names, at the default service's `--cpus 4.0 --memory 8.0g --memory-swap
8.0g`, so that row described a container the stack did not start.

**What closed it.** `llama-subagent-qwen` now declares `cpus`, `mem_limit` and `memswap_limit`
written exactly as `llama-subagent` does, and passes `--threads` from its `cpus` substitution. Each
server is capped at the whole budget; whether the two should instead share one budget is the
question ADR-0012 left open with its single-executor position.

## History

- 2026-09-08: opened by re-reading
  [R-559](559-the-cpu-row-applies-the-cpu-quota-and-not-the-memory-cap.md), which measured the
  default CPU subagent server against the caps the override sets on it
  ([ADR-0004](../../adr/ADR-0004-model-lineup.md)).
- 2026-09-11: read against the rendered stack. `docker compose config` over the base, subagents and
  roster files rendered `llama-subagent` with `cpus: 4` and both memory limits at 8589934592, and
  `llama-subagent-qwen` with none of the three; no container was up, so nothing had run the two
  side by side. The trigger's grep was repaired, its wide pattern having matched the entry's
  `"cpus": 2.0` ask on the roster line and read it as a cap. The pick's CPU row drawn the same
  night, recorded in
  [R-628](628-the-subagent-cpu-servers-thread-count-is-not-set-from-its-quota.md), measured the
  default server's 24 unlimited threads inside a quota of four being throttled in 14,308 of 14,520
  periods, 1560.15 s against 114.08 s with the count fixed. Since the alternate ran the same 24
  threads with no quota, adding the three caps alone would have given it that cost, so the caps and
  a thread count read from one constant belong in one change.
- 2026-09-11: done, in one change with the thread count, which also closed
  [R-628](628-the-subagent-cpu-servers-thread-count-is-not-set-from-its-quota.md). The previous
  bullet's reasoning about the alternate was wrong, measured: uncapped with 24 threads it decoded
  at 2.99 to 3.46 tok/s on one slot and 2.75 per slot on two, against 22.56 to 22.66 and 17.18 to
  17.28 under the three caps and four threads, so the change made it faster rather than costing it
  anything. The constant scan counts the two new CPU values and the two memory ones in the roster
  file. Recorded in [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md) decision 9.
