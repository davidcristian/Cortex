# Check the sidecar's stop bounds against the control deadline

**Status:** done 2026-08-09
**Area:** inference-model-manager
**Origin:** [ADR-0053](../../adr/ADR-0053-model-host-supervisor.md)

A supervisor `stop` answers only once the child is reaped, so it can legitimately take
`probe_timeout_s + stop_grace_s + reap_timeout_s`. If that sum reaches the brain's
`CORTEX_MODELHOST_TIMEOUT_S`, the control client times out, `swap_in` raises `ModelHostError`,
and a handoff whose eviction was working aborts. The shipped defaults are safe (5 + 10 + 30 = 45
below 60, all three measured), and the rule was written in the runbook, the compose override's
comment and the `DEFAULT_MODELHOST_TIMEOUT_S` comment. What was missing was enforcement, because
the two sides are separate processes' environments.

**Shipped 2026-08-09**, ahead of its trigger
([ADR-0053](../../adr/ADR-0053-model-host-supervisor.md) decision 11). The account of the code
was checked first and held on every point: `api.py` published two of the three terms,
`probe_timeout_s` lived on `ModelHostConfig` and was used only as the probe client's
`httpx.Timeout`, `build_control_client` compared its float with nothing, and 5 + 10 + 30 = 45
still cleared 60.

The third term joined `GET /health`, the three travel as one core value (`ControlBounds`, with
`worst_case_stop_s` and a strict `clears(deadline_s)`), a fifth `ModelHost` verb reads them back
off that same body, and `check_control_deadline` in `swap_builders.py` checks the runtime on its
way out of the builder.

Two things the entry got wrong, both in the direction of over-caution. The check could not live
inside `build_control_client`, which is synchronous and is itself what builds the client the
question would have to be asked with, so it is a sibling in the same module that the composition
root passes the runtime through. And the cost it named, a wiring-time dependency on the sidecar
answering, largely does not exist, because `recover_handoffs` already calls that sidecar at
startup before the gRPC server serves.

Only a mismatch the host reports is fatal. An unreachable host is logged at warning and let through,
since a restart policy fixes it; a host reporting no bounds is the scripted twin; and a static
mispairing that no restart can fix stops the runtime from serving, since its failure is otherwise
intermittent, a stop paying the whole grace only when the tier it evicts was busy.

## History

- 2026-07-18: Opened by the audit round on the model-host sub-slice, which found the pairing had a
  third term and added the `GET /health` reporting that would make the check possible.
- 2026-07-18: The third term is the probe timeout, and the mechanism that adds it to a stop was
  recorded with the finding: a `status` queued on the same per-model lock probes inside that stop.
- 2026-08-07: Its stated price, a wiring-time dependency on reaching the sidecar, was quoted by
  the co-residency fit entry and turned out not to transfer, that check having gone in at the swap
  instead.
- 2026-08-09: Shipped ahead of its own trigger and its line in the index's fix-when-it-matters
  bucket was removed. One out and none in, the one staleness left, a sidecar that restarts under a
  running brain with a different environment, having been folded into
  [R-114](114-reconverge-residency-on-restart.md), which shares its cause and its fix.
