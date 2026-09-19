# Reconverge residency when the sidecar restarts under it

**Status:** done 2026-08-09
**Area:** inference-model-manager
**Origin:** [ADR-0053](../../adr/ADR-0053-model-host-supervisor.md)

Observed live: `kill -9` on the supervisor daemon ended its container, both `llama-server`
children died with it and VRAM returned to baseline, `restart: unless-stopped` revived it, and its
boot default started the cortex again. That direction recovers on its own. The other one did not.
`SwappingModelManager` held `_resident`, `_scope_model` and `_handoff_claimed` as instance
attributes, and `recover_handoffs` ran only at brain startup, so a sidecar that restarted mid
handoff left the brain recording the deep model as resident and holding a claim while the fresh
sidecar served the cortex. The turn then failed at the backend, the swap back's `stop` and `start`
were harmless against a sidecar that had already done both, and the claim was released in the
conductor's `finally`, so the failure was self-limiting. What was lost was that one handoff, plus
a window where `Health` reported the wrong residency. With escalation off, the default, nothing
was at stake, because the plain `SingleResidentModelManager` holds no residency state; a turn
answered normally straight after a restart.

It was recorded to wait for a sidecar that restarts under a handoff in flight over the supervisor
backend, from an OOM kill, a crash or an operator's `docker compose restart model-host`, seen more
than once. It shipped before that happened.

**Both halves shipped 2026-08-09**
([ADR-0053](../../adr/ADR-0053-model-host-supervisor.md) decision 12). The second half had joined
this entry hours earlier: the deadline pairing is checked once at wiring time against the bounds
the sidecar reports, so a sidecar that comes back with a changed environment leaves that check as
stale as it leaves residency, and one identifier closes both.

What shipped is a boot id, `uuid4().hex` minted per `ModelSupervisor` instance and therefore per
daemon process, published on `GET /health`, read by a sixth `ModelHost` verb shaped like the
fifth, and compared for equality by a `BootWatch` the manager holds (`residency_watch.py`). A
replacement converges residency, publishes what convergence observed onto the manager's own
resident and report, and re-reads the stop bounds against `CORTEX_MODELHOST_TIMEOUT_S`, which now
sits on `ResidencyPlan` so the boot check and this one cannot compare different numbers. It is
asked at the top of `_swap_in`, before anything is evicted, so a refusal leaves the cortex
serving, and it is seeded by `publish_boot_residency` so the first handoff has a daemon to compare
against.

Three things the entry did not say shaped the result. A counter was not usable, since a counter in
a restarted process starts again at the number the comparison exists to notice, which is why the
identifier is random. `converge_residency` cannot be called speculatively, because it stops and
restarts every `evict_models` tier, which is exactly what a `coresident` plan exists not to do to
its peers, so a first observation had to be a seed and the seeding had to happen at boot. And the
scope hazard is narrower than it looks: the reconciliation runs inside the one scope there can be,
a concurrent one having been refused by the handoff claim and by `_begin_scope`, so `_scope_model`
never needs rebuilding and what does is the resident and the report.

What did not close is staleness with no restart behind it, filed as
[R-116](116-reconciliation-without-a-turn.md). Two report cases have no replacement to notice: an
operator who brings the cortex back by hand after a failed restore
(`docs/runbooks/model-swap.md` step 2), which leaves the report saying the usual assistant could
not be reloaded until the brain restarts; and a boot whose recovery could not confirm the cortex,
which publishes `RESIDENCY_BOOT_FAILED` and stays amber even if the cortex comes up a minute later
on its own. Both are deliberately a false amber rather than a false green, and deliberately not
paid for with a probe per `Health`, which the ADR priced at up to 5.80 s against a 5 s recheck.
The lease is untouched by that publish, so a machine that is in fact serving still serves turns
while the indicator is wrong. The reconciliation is reachable only through a handoff, which a
brain with nothing resident cannot start.

## History

- 2026-07-18: Opened by the model-host sub-slice and observed live rather than reasoned about; the
  area went 5 to 6.
- 2026-07-18: The honesty-surfaces sub-slice made `Health` answer from the manager's published
  report, so the wrong-residency half stopped being a prediction, and that same change added two
  more ways for the report to go stale, both with this same fix.
- 2026-07-19: Given a line in the index's pickup order.
- 2026-08-09: Took the deadline-pairing staleness rather than letting it open an entry of its own,
  since one identifier closes both.
- 2026-08-09: Both halves shipped hours later the same day, in almost the shape the entry
  proposed, with the three corrections above. It opened one entry in its place, so the area count
  held.
