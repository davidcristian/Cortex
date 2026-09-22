# The deep model's clearing deciding the cortex's result

**Status:** done 2026-08-11
**Area:** resource-governance
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)

A `status` or `stop` of the deep tier that raised answered `False` without asking about the cortex at
all. That is right for an unreachable host and right for a deep model that really is resident and
cannot be stopped. It is wrong for one reachable case: a deployment that sets `CORTEX_ESCALATION=1`
without naming `CORTEX_MODEL_FILE_BRAIN` gets a daemon that 404s that tier for ever, so every boot is
amber over a cortex that is serving. The port could not tell the two apart, since `ModelHostError`
covered both an unknown model and an unreachable host.

Fixed on 2026-08-11, recorded at [ADR-0053](../../adr/ADR-0053-model-host-supervisor.md) decision
14. The port has `ModelNotHostedError`, a subclass of `ModelHostError` so that every caller which
cannot use the distinction catches what it always caught, and the adapter raises it for a 404 on a
per-model route and for nothing else. Boot recovery clears the deep tier best effort in that one
case, so an unrostered deep tier is a green boot plus one `ERROR` naming both
`CORTEX_MODEL_FILE_BRAIN` and `CORTEX_ESCALATION`, while a deep model that will not stop, an
unreachable sidecar, and a cortex id the roster does not have all stay amber.

The entry's account of the tree held to the line, checked before anything was designed: the flat
error, the single `try`, and the sidecar's own `UnknownModelError` already crossing the wire as a 404
the adapter discarded.

The amber dot was the cheap half. Driven one call further, through a real `swap_scope` against a real
supervisor over HTTP, the shipped code met that same 404 in the swap back's stop of the model it had
swapped in, failed the restore, failed its retry, and raised `ResidencyRestoreError` with the cortex
left stopped and the brain reporting that recovery was manual. So a deployment that merely could
not escalate lost its assistant at the first attempt to. The fix therefore reaches `residency_moves.py` as well:
the swap back skips exactly that one failure, since a tier the host never had can hold no card.

The same 404 also reaches the tier retry for a peer, which then asks a roster that cannot grow every
interval. Nothing is harmed, so that policy question is named on the retry entry above.

## History

- 2026-08-09: Opened by the boot-result close, which made the peers' clearing best effort and
  deliberately left the deep model's fatal.
- 2026-08-11: Closed ahead of its trigger and built exactly as its text specified. Three of the seven
  measured mutations cover the direction that would have been worse to get wrong. One entry opened
  in its place, the brain forgetting what it learned.
- 2026-08-11: The same pass found the entry had understated itself, and the restore defect above was
  fixed with it and recorded at the ADR rather than here.
