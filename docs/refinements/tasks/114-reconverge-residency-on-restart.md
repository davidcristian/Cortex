# Reconverge residency when the sidecar restarts under it

**Status:** landed 2026-08-09
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Opened 2026-07-18 by the model-host sub-slice, and observed live rather than reasoned
about: `kill -9` on the supervisor daemon ended its container (both `llama-server` children died
with it and VRAM returned to baseline), `restart: unless-stopped` revived it, and its boot default
started the cortex again from a clean slate. That direction reconverges by construction. The other
one does not. `SwappingModelManager` holds `_resident`, `_scope_model` and `_handoff_claimed` as
instance attributes ([residency.py](../../../brain/packages/core/src/cortex_core/residency.py)), and
`recover_handoffs` runs **only** at brain startup
([wiring.py](../../../brain/packages/orchestrator/src/cortex_orchestrator/wiring.py)), so a sidecar
that restarts mid handoff leaves the brain believing the deep model is resident and holding a
claim while the fresh sidecar serves the cortex. The turn then fails at the backend (the deep
tier's endpoint answers nothing), the swap back's `stop`/`start` are idempotent and harmless
against a sidecar that already did both, and the claim is released in the conductor's `finally`,
so the failure is honest and self-limiting; what is lost is that one handoff, plus a window where
`Health` misreports residency. That last half stopped being a prediction on 2026-07-18: the
honesty-surfaces sub-slice made `Health` answer from the manager's published report, so a brain
whose beliefs a sidecar restart invalidated now shows an amber dot naming a swap that is not
happening (or a green one over a GPU that lost its model), until the handoff fails and the scope
restores. **Nothing is at stake with escalation off** (the default), because the plain
`SingleResidentModelManager` holds no residency state: a sidecar restart is then invisible to the
brain, which was confirmed live (a turn answered normally straight after the restart).
**What would close it:** the daemon exposing a boot id or generation counter on `GET /health`, the
adapter carrying it, and the manager treating a change in it as "everything I believe about
residency is stale, converge again" (which is `converge_residency`, already written, called from
somewhere other than startup). That is a wire addition plus a caller, not a port change. The
residency state that landed on 2026-07-18 is where the answer would be published, but it did
**not** close any of this: `ResidencyReport` says what the GPU is serving in one line for a human,
and carries no generation to compare a boot id against. Its writers are the swap itself and, from
that day's audit repair, boot recovery publishing what it observed (`publish_boot_residency`),
which is a *startup* observation and so still leaves nothing that re-reads the machine while the
process runs. The same landing added two ways for the report to go stale, both with this same
fix. After a restore that gave up, an operator who brings the cortex back by hand
(`docs/runbooks/model-swap.md` step 2) leaves the report saying the usual assistant could not be
reloaded until the brain restarts, which is why that runbook's recovery ends by restarting it.
And a boot whose recovery could not confirm the cortex publishes `RESIDENCY_BOOT_FAILED`, which
is honest at the instant it is written and stays amber even if the cortex comes up a minute
later on its own: deliberately a false amber rather than a false green, and deliberately not
paid for with a probe per `Health` (the ADR priced that at up to 5.80 s against a 5 s recheck).
The lease is untouched by that publish, so a machine that is in fact serving still answers turns
while the dot is wrong.
**Trigger:** a sidecar that restarts (an OOM kill, a crash, an operator's `docker compose restart
model-host`) while a handoff is in flight over the supervisor backend, seen more than once.
**A second staleness joined this entry on 2026-08-09** rather than opening one of its own,
because it has the same cause and the same fix: the deadline pairing below is now checked once at
wiring time against the bounds the sidecar reports, so a sidecar that restarts under a running
brain with a **changed** environment leaves that check as stale as it leaves residency. A
generation counter on `GET /health` closes both at once, the brain re-reading whatever the fresh
daemon says.
**Both halves landed 2026-08-09, hours after the second one joined
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) host-generation addendum).** The entry's account of
the code was re-derived first and held on every point: `converge_residency` was written and
called from one place, boot recovery, which had itself moved into `swap_builders.py`;
`SwappingModelManager` held `_resident`, `_scope_model` and the report as instance state; and
`GET /health` carried no identity field at all. What shipped is a **boot id**, `uuid4().hex`
minted per `ModelSupervisor` instance and therefore per daemon process, published on that route,
read by a sixth `ModelHost` verb shaped like the fifth, and compared for equality only by a
`BootWatch` the manager holds (`residency_watch.py`). A replacement converges residency,
publishes what convergence observed onto the manager's own resident and report, and re-reads the
stop bounds against `CORTEX_MODELHOST_TIMEOUT_S`, which now rides `ResidencyPlan` so the boot
check and this one cannot compare different numbers. It is asked at the top of `_swap_in`, before
anything is evicted, so a refusal leaves the cortex serving; it is seeded by
`publish_boot_residency`, so the first handoff has a daemon to compare against.
**Three things the entry did not say, all of which shaped the result.** A counter was not
usable at all, since a counter in a restarted process starts again at the number the comparison
exists to notice, which is why the identifier is random. `converge_residency` is **not** free to
call speculatively, because it stops and restarts every `evict_models` tier, which is exactly
what a `coresident` plan exists not to do to its peers, so a first observation had to be a seed
rather than a change and the seeding had to happen at boot. And the scope hazard is narrower than
it looks: the reconciliation runs inside the one scope there can be, a concurrent one having been
refused by the handoff claim and by `_begin_scope`, so `_scope_model` never needs rebuilding and
the beliefs that do are the resident and the report.
**What did not close is the staleness with no restart behind it**, which is the residue this
opened and which is filed as its own entry below: the two report cases quoted above (an operator
who recovers by hand, and a cortex that comes up on its own after a failed boot) have no
replacement to notice, and the reconciliation is reachable only through a handoff, which a brain
with nothing resident cannot start.

## Trail

- 2026-07-18: Opened by the model-host sub-slice and observed live rather than reasoned about; the
  area went 5 to 6 rather than decrementing for the process-lifecycle half that landed with the same
  sub-slice.
- 2026-07-18: The honesty-surfaces sub-slice made `Health` answer from the manager's published
  report, so the misreported-residency half stopped being a prediction, and that same landing added
  two more ways for the report to go stale, both with this same fix.
- 2026-07-19: Given a line in the index's pickup order, which it had lacked since it was written up.
- 2026-08-09: Took a second staleness rather than letting it open an entry of its own, the
  deadline-pairing check that landed that day being read once at wiring time, so a sidecar coming
  back with a changed environment leaves it as stale as it leaves residency and one generation
  counter closes both.
- 2026-08-09: Both halves landed hours later the same day, in almost the shape the entry's own text
  proposed. The one correction is that a counter was never usable, since a counter in a restarted
  process starts again at the number the comparison exists to notice, so the identifier is a random
  per-process boot id; and what the text did not price is that `converge_residency` cannot be called
  speculatively, stopping and restarting every evictable tier being exactly what a co-resident plan
  exists not to do to its peers, so a first observation is a seed and the boot publish is what seeds
  it. It opened one entry in its place and the area count therefore held.
