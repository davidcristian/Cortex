# The deep model's clearing deciding the cortex's verdict

**Status:** landed 2026-08-11
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

The deep model's clearing still decides the cortex's verdict at boot. Opened 2026-08-09 by the close
above, which made the peers' clearing best effort and deliberately left `plan.brain_model`'s fatal:
a `status` or `stop` of the deep tier that raises answers `False` without asking about the cortex at
all. That is right for the shape it was written for, an unreachable host, and right in the corner
that matters, a deep model that really is resident and really cannot be stopped, since a boot that
reported green over a card still holding it would be the opposite error. It is wrong for one
reachable shape: a deployment that sets `CORTEX_ESCALATION=1` without naming
`CORTEX_MODEL_FILE_BRAIN` gets a daemon that 404s that tier for ever, so every boot is amber over a
cortex that is serving. The reason it is recorded rather than fixed is that the port cannot tell the
two apart: `ModelHostError` covers both an unknown model and an unreachable host, and guessing from
a message string is worse than the wrong verdict. The fix is therefore a narrower failure on the
port (a typed "this host does not serve that id", which the sidecar already distinguishes as a 404
and the adapter already collapses), after which an unrostered deep tier is reported as a
configuration fault instead of an amber dot. The trigger is the first deployment observed booting
amber with a cortex that is serving, or the same port distinction being wanted for any other reason.
**It landed 2026-08-11, ahead of that trigger, recorded at the [ADR-0030 unrostered-tier
addendum](../../adr/ADR-0030-brain-handoff.md).** The port has the narrower failure the entry asked
for, `ModelNotHostedError`, a subclass of `ModelHostError` so that every caller which cannot use the
distinction goes on catching what it always caught, and the adapter raises it for a 404 on a
per-model route and for nothing else. Boot recovery clears the deep tier best effort in that one
shape, so an unrostered deep tier is a green boot plus one `ERROR` naming both
`CORTEX_MODEL_FILE_BRAIN` and `CORTEX_ESCALATION`, while a deep model that is resident and will not
stop, an unreachable sidecar, and a cortex id the roster does not have all stay amber. Three things
about it, one of them the entry's own account and two of them things it could not have known.
**Its account of the tree held to the line**, checked before anything was designed: the flat error,
the single `try`, and the sidecar's own `UnknownModelError` already crossing the wire as a 404 that
the adapter collapsed. So this was a port change and an adapter that stops discarding the
distinction, which is why it was small.
**The amber dot was the cheap half.** Driven one call further, through a real `swap_scope` against a
real supervisor over HTTP, the shipped code met that same 404 in the swap back's stop of the model
it had swapped in, failed the restore, failed its retry, and raised `ResidencyRestoreError` with the
cortex left stopped and the seam saying recovery was manual. So a deployment that merely could not
escalate lost its assistant at the first attempt to, and the fix therefore reaches
`residency_moves.py` as well: the swap back skips exactly that one failure, since a tier the host
never had can hold no card, and the swap in names the configuration fault rather than blaming the
machine.
**The distinction has a second site, and it is left open where it belongs.** The same 404 reaches
the tier retry for a peer, which then asks a roster that cannot grow, every interval, for ever.
Nothing is harmed and the log records it each pass, so what is open is a policy question about a
tier that can never come back, and it is named on the retry entry above rather than filed as an
entry of its own.

## Trail

- 2026-08-09: Opened by the boot-verdict close, which made the peers' clearing best effort and
  deliberately left `plan.brain_model`'s fatal.
- 2026-08-11: Landed ahead of its trigger, recorded at the
  [ADR-0030 unrostered-tier addendum](../../adr/ADR-0030-brain-handoff.md) and built exactly as its
  text specified, the port gaining `ModelNotHostedError` as a subclass raised for a 404 on a
  per-model route and for nothing else. An unrostered deep tier is a green boot and a loud line
  rather than an amber dot, and three of the seven measured mutations pin the direction that would
  have been worse to get wrong. One entry opened in its place, the brain forgetting what it learned.
- 2026-08-11: The same close found the entry had understated itself. The swap back's stop of the
  model it had swapped in met that same 404, failed the restore, failed its retry, and raised
  `ResidencyRestoreError` with the cortex left stopped and the seam saying recovery was manual, so a
  deployment that merely could not escalate lost its assistant at the first attempt to. That is a
  defect rather than a deferral, fixed in the same pass and recorded at the ADR instead of here.
