# The roster alternate's CPU server carries neither cgroup cap

**Status:** open, fix when it bites
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)
**Trigger:** a deployment running the roster override alongside the default subagent server on a
box where the two together would exceed the memory the default one is capped at, or any reading
that attributes a roster-alternate measurement to the caps the default service sets. Read it with
`grep -n 'cpus\|mem_limit\|memswap_limit' docker/docker-compose.subagents-roster.yml`, which
matches nothing today.

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
Qwen3.5-2B, which is the artifact this override names, at the default service's `--cpus 4.0`, so
that row describes a container the stack does not start.

**What would close it.** The same three lines on `llama-subagent-qwen`, spelled the way the default
service spells them, and a `Site` reaching them if the constant scan is to hold the second pair too.
Whether both servers should instead share one budget is the question ADR-0012 deferred with the
single-executor stance, and answering that would close this differently.

## Trail

- 2026-09-08: opened by the re-reading of
  [R-559](559-the-cpu-row-carries-the-cpu-quota-and-not-the-memory-cap.md), recorded in the
  [ADR-0004 lineup-trigger addendum](../../adr/ADR-0004-model-lineup.md#addendum-2026-09-08-three-lineup-triggers-re-read-and-a-memory-cap-already-at-90-of-its-limit).
