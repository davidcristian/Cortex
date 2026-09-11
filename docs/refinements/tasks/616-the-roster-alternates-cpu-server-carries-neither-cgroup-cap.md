# The roster alternate's CPU server carries neither cgroup cap

**Status:** landed 2026-09-11
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)

Opened 2026-09-08 by the re-reading of
[R-559](559-the-cpu-row-carries-the-cpu-quota-and-not-the-memory-cap.md), which measured the default
CPU subagent server against the caps that override sets on it.

`llama-subagent` in `docker/docker-compose.subagents.yml` is capped at `cpus: 4.0`, `mem_limit` and
`memswap_limit` at 8 GiB, the brain's own `DEFAULT_CPU_BUDGET` and `DEFAULT_MEM_BUDGET_GB`, which
`scripts/crosscheck.py` holds to those constants. `llama-subagent-qwen` in
`docker/docker-compose.subagents-roster.yml` is a second CPU llama-server, layered on top of that
file rather than merged into that service, and it declares none of the three. It gets the host's
whole CPU and unlimited memory.

**Why this is not only a compose omission.** The scheduler charges a roster entry's declared ask,
`cpus: 2.0, memory_gb: 1.5` for this entry, against the same soft budget it charges the default
entry's, so the brain's ledger already assumes both servers live inside one budget. Nothing on the
host enforces that assumption for the second one. The injection harness draws a CPU row for
Qwen3.5-2B, which is the artifact this override names, at the default service's `--cpus 4.0
--memory 8.0g --memory-swap 8.0g`, all three read off the brain's `DEFAULT_CPU_BUDGET` and
`DEFAULT_MEM_BUDGET_GB`, so that row describes a container the stack does not start.

**What would close it.** The same three lines on `llama-subagent-qwen`, spelled the way the default
service spells them, and a `Site` reaching them if the constant scan is to hold the second pair too.
Whether both servers should instead share one budget is the question ADR-0012 deferred with the
single-executor stance, and answering that would close this differently.

## Trail

- 2026-09-08: opened by the re-reading of
  [R-559](559-the-cpu-row-carries-the-cpu-quota-and-not-the-memory-cap.md), recorded in the
  [ADR-0004 lineup-trigger addendum](../../adr/ADR-0004-model-lineup.md#addendum-2026-09-08-three-lineup-triggers-re-read-and-a-memory-cap-already-at-90-of-its-limit).
- 2026-09-11: read against the rendered stack and not fired. `docker compose config` over the
  base, subagents and roster files renders `llama-subagent` with `cpus: 4` and both memory
  limits at 8589934592, and `llama-subagent-qwen` with none of the three; no container was up,
  so nothing has run the two side by side. The trigger's grep was repaired, its wide spelling
  having matched the entry's `"cpus": 2.0` ask on the roster line and read as a cap, and the
  harness sentence above now carries the two memory caps the CPU row has passed beside the
  quota since the entry about the quota and not the memory cap landed. **Where this meets the
  thread-count entry.** The pick's CPU row drawn tonight, recorded in
  [R-628](628-the-subagent-cpu-servers-thread-count-is-not-pinned-to-its-quota.md), measured
  the default server's 24 unpinned threads inside a quota of four being throttled in 14,308 of
  14,520 periods, 1560.15 s against 114.08 s with the count pinned. The alternate runs the same
  24 threads with no quota to throttle against, so today it is the one CPU server here that
  does not pay that cost, and adding the three caps here on their own would hand it that cost.
  The caps and a pinned thread count read from one constant therefore belong in one change,
  and that entry's pin has nothing to be pinned to on this server until these caps exist. Both
  entries now say so.
- 2026-09-11: landed in one change with the thread count, which closed
  [R-628](628-the-subagent-cpu-servers-thread-count-is-not-pinned-to-its-quota.md).
  `llama-subagent-qwen` now declares `cpus`, `mem_limit` and `memswap_limit` spelled exactly as
  `llama-subagent` does, and passes `--threads` from its `cpus` substitution; the grep the
  trigger carried now matches the three cap lines in the roster file. The previous bullet's
  reasoning was wrong
  about the alternate, measured: uncapped with 24 threads it decoded at 2.99 to 3.46 tok/s on one
  slot and 2.75 a slot on two, against 22.56 to 22.66 and 17.18 to 17.28 under the three caps and
  four threads, so the change made it faster rather than handing it a cost. The constant scan
  counts the two new CPU spellings and the two memory ones in the roster file. Each server is
  capped at the whole budget, and the split the last paragraph above names stays ADR-0012's
  deferred question. Recorded in the
  [ADR-0018 alternate-caps addendum](../../adr/ADR-0018-heterogeneous-subagents.md#addendum-2026-09-11-the-roster-alternates-server-carries-the-defaults-three-caps-and-its-thread-count).
