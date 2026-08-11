# Reach the residency reconciliation without a turn

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** A second visit to the manual-recovery path, or a report observed stale by a user rather than by a reading of the code.

Opened 2026-08-09 by the entry above landing, and it is the half a boot id cannot answer. The
reconciliation fires on one event, a daemon naming a different boot, and at one place, the top of
`_swap_in`. Both are deliberate (a probe per `Health` was priced at up to 5.80 s against a 5 s
recheck, and converging speculatively bounces a co-resident plan's peers), and together they
leave two states unreachable. **The first is the expensive one.** After a restore that gave up,
`_set_resident(None, RESIDENCY_LOST)` means `acquire` raises `ModelUnavailableError` for every
model, so no turn runs, so no handoff starts, so nothing ever reaches the reconciliation even
once the sidecar has genuinely been replaced and is serving the cortex again. That is why
`docs/runbooks/model-swap.md`'s manual recovery still ends by restarting the brain. **The second
is only a dot:** a boot that could not confirm the cortex publishes `RESIDENCY_BOOT_FAILED` and
stays amber if the cortex comes up a minute later by itself, with the lease deliberately left
forgiving so turns still run. **What would close it:** a reconciliation on the refusal path
rather than only inside a swap, which is a cold path (a refused acquire has already failed, so a
`GET /health` there costs nothing anyone is waiting on) but is genuinely delicate, because
`_claim` holds the residency condition and would have to release it to do I/O, and because the
same refusal is reached mid swap while the deep model is loading, where converging would stop
the very load in flight. So it wants a gate on "no scope is active" and its own concurrency
argument, and possibly an operator-facing re-converge verb instead, which needs no lock
reasoning at all. **Trigger:** a second visit to the manual-recovery path, or a report observed
stale by a user rather than by a reading of the code.

## Trail

- 2026-08-09: Opened by the residency entry above landing, as the half a boot id cannot answer: the
  reconciliation fires on one event and at one place, so a brain whose restore gave up refuses every
  acquire and the state that most needs reconciling is the one state that can never reach it, which
  is why the runbook's manual recovery still ends by restarting the brain. One out and one in, so
  the area count held at 7.
- 2026-08-09: A trigger sweep of the index's fix-when-it-bites bucket read that bucket against the
  tree and fired nothing. This entry reached that verdict inside a group rather than under its own
  name, the residency and model-manager entries each recent close opened, whose triggers are
  live-observation shaped, a deployment doing something rather than a file saying something, so no
  reading of the code settles them.
