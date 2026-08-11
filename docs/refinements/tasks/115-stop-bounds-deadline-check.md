# Check the sidecar's stop bounds against the control deadline

**Status:** landed 2026-08-09
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Opened 2026-07-18 by the audit round on the
model-host sub-slice. A supervisor `stop` answers only once the child is reaped, so it can
legitimately take `probe_timeout_s + stop_grace_s + reap_timeout_s`, and if that sum reaches the
brain's `CORTEX_MODELHOST_TIMEOUT_S` the control client times out, `swap_in` raises
`ModelHostError`, and a handoff whose eviction was working aborts. The shipped defaults are safe
(5 + 10 + 30 = 45 below 60, all three measured), and the rule is now written in three places
(the runbook, the compose override's comment, and the `DEFAULT_MODELHOST_TIMEOUT_S` comment), so
what is deferred is **enforcement**, not the knowledge. It was left unenforced because the two
sides are separate processes' env and neither can read the other's, which is the reason the
original landing gave. That reason is now weaker in one direction: `GET /health` reports the two
stop bounds the daemon was actually given, so the brain **could** read them at wiring time and
refuse to boot (or log loudly) when its own deadline does not clear their sum plus the probe
timeout. **What would close it:** the probe timeout on that same body (it belongs to the health
probe's client rather than to the supervisor, so it needs a small widening of what the daemon
reports), and a check in `swap_builders.build_control_client` that fails closed exactly as the
endpoint validator does. The cost is that the brain would then depend on the sidecar answering
at wiring time, which today it deliberately does not. **Trigger:** a user tuning either side's
timing, or a second deployment shape where the defaults do not hold, and any report of a handoff
aborting with `ModelHostError` on an eviction that in fact completed.
**This landed 2026-08-09, ahead of its trigger and in almost the shape its own text proposed
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) deadline-pairing addendum).** Its account of the
code was re-derived first, as this backlog demands, and held on every point: `api.py` published
two of the three terms, `probe_timeout_s` lived on `ModelHostConfig` and was spent only as the
probe client's `httpx.Timeout`, `build_control_client` compared its float with nothing, and
5 + 10 + 30 = 45 still cleared 60. What shipped is the third term on `GET /health`, the three
travelling as one core value (`ControlBounds`, with `worst_case_stop_s` and a strict
`clears(deadline_s)`), a fifth `ModelHost` verb reading them back off that same body, and
`check_control_deadline` in `swap_builders.py` gating the runtime on its way out of the builder.
Two things the entry got wrong, both in the direction of over-caution. The check could not live
**in** `build_control_client`, which is synchronous and is the thing that builds the client the
question would have to be asked with, so it is a sibling in the same module that the composition
root passes the runtime through. And the cost it named, a wiring-time dependency on the sidecar
answering, largely does not exist: `recover_handoffs` already calls that sidecar at startup
before the seam serves. What it deliberately does not do is raise, so the real question was
whether to make a tolerant boot dependency fatal, and the answer is only for an **answered**
mismatch: an unreachable host is logged at warning and let through (a restart policy heals it), a
host reporting no bounds is the scripted twin, and a static mispairing that no restart can heal
refuses to serve, since its failure is otherwise intermittent (a stop pays the whole grace only
when the tier it evicts was busy). The one staleness left, a sidecar that restarts under a
running brain with different env, is the same staleness with the same fix as the residency entry
above and is folded into it rather than counted as a new deferral.

## Trail

- 2026-07-18: Opened by the audit round on the model-host sub-slice, which found the pairing had a
  third term and added the `GET /health` reporting that would make the check possible, so what was
  deferred is enforcement rather than the knowledge.
- 2026-07-18: The third term is the probe timeout, and the mechanism that adds it to a stop was
  recorded with the finding: a `status` queued on the same per-model lock probes inside that stop.
- 2026-08-07: Its stated price, that the brain would then depend on the sidecar answering at wiring
  time, was quoted by the co-residency fit entry and turned out not to transfer, that check having
  landed at the swap instead.
- 2026-08-09: Landed ahead of its own trigger and its line in the index's fix-when-it-bites bucket
  was struck, its account of the code re-derived first and held: the third term joined the health
  body, the three became one core value with the rule as a method on it, a fifth `ModelHost` verb
  reads them back, and the composition root refuses to serve on an answered mismatch while an
  unreachable sidecar stays tolerated exactly as boot recovery already argued it must be. One out
  and none in, the one staleness left having been folded into the residency entry that shares its
  cause and its fix.
