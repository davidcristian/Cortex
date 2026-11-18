# A spawn is leased a GPU subagent server that is not serving

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)
**Verified:** 2026-11-18

`MultiServerModelManager.acquire` (`brain/packages/core/src/cortex_core/model.py`) leases the
server with the most free slots, the first listed on a tie. It reads nothing about whether a
server is serving. With two servers of one slot and the first one down, every spawn that runs
alone is leased the first server, fails, and runs again on the CPU, while the second server is
idle. Only the second spawn of a batch of two reaches the server that works.

What limits it today:

- Under escalation the recheck pass finds a stopped tier within `CORTEX_SWAP_TIER_HEAL_S`, closes
  GPU placement for every server through `BaselineTiers.mark_missing`, and starts the tier again.
  The cost is one interval of CPU runs, for both servers and not only the one that stopped.
- With escalation off nothing rechecks or restarts a subagent server, since the model host's
  restart budget names the cortex alone. The state lasts until the model host is restarted
  ([R-1248](1248-with-escalation-off-nothing-starts-the-gpu-subagent-servers.md)).

## Reproduction

Drawn on 2026-11-18 with escalation off, `subagent-gpu` stopped, and `subagent-gpu-2` started by
hand and `ready`. Two delegated turns of one spawn each both logged
`a GPU-placed subagent did not answer; re-running it once on the CPU`, and the brain's log has no
`model now served by engine build` line for the second server's address. Log:
`~/.cache/cortex-run/2026-11-18/slot8/logs/onedead.txt`.

## What would close it

Either of these, in the core behind the `ModelManager` port:

- a lease that passes over a server whose last request failed to connect, until a request to it
  answers again;
- a record per server in `BaselineTiers`, so the placer and the lease close one server and not the
  whole tier.

Not drawn: a spawn admitted just after a swap back, while both servers are still loading.
`restart_evicted` marks a tier as serving when its start is accepted, and the two servers read
`loading` for several samples after the cortex was `ready` again
(`~/.cache/cortex-run/2026-11-18/slot8/logs/watch-swap.txt`).

## History

- 2026-11-18: filed by the audit of the two-server default, which drew the reproduction above.
