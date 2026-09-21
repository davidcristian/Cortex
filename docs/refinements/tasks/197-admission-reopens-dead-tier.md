# Admission reopening onto a tier that would not restart

**Status:** done 2026-08-09
**Area:** resource-governance
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)

Restarting an evicted tier after a swap back is deliberately best effort
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) decision 4: a tier that will not come back must not
be reported as the cortex being gone), so a `ModelHostError` on that start is logged and swallowed,
and `undrain` then reopens admission onto a subagent server that is not running. The next delegated
run fails at its backend and turns into an `ok=False` result, and nothing retried the tier until the
next handoff or a restart.

Fixed on 2026-08-09, recorded at [ADR-0054](../../adr/ADR-0054-baseline-residency.md) decision 3 and
at [ADR-0012](../../adr/ADR-0012-resource-governance.md) decision 13. A peer the swap back could not
restart is recorded in `BaselineTiers` (`residency_tiers.py`), which closes GPU placement, names the
tier on a serving `Health` reply, and is retried every `CORTEX_SWAP_TIER_HEAL_S` (30 s) by
`TierRechecker` until a pass sees the tier `ready`.

Two corrections to the entry. The scheduler port really is untouched, but the placer port is not:
`place` is synchronous, lock-free and argument-poor by design, so nothing can ask it whether a tier
is up, and the only shape that fits is being told. `SubagentPlacer` gained `close_gpu()` and
`open_gpu()`, deliberately not expressed as a charge, since a charge large enough to crowd the cap
out would say "no room" where the truth is "no server", and would be reversed by the next successful
`charge_baseline`. And widening `ResidencyReport` does not work, for a lifetime reason rather than a
shape reason: that value is republished at every residency transition, so a fault written into it
would be dropped by the next swap in. The record lives beside the report and is combined with it on
read, which also keeps the swap to one writer of what the GPU is serving.

The distinction the entry never named is the one the design turns on: a tier that is down versus one
that is merely evicted. Only a `start` that raised marks a tier, only a serving report is annotated,
and the handoff window is covered by the drain and the charge, so a tier stopped for the length of a
swap never reads as a fault.

Nothing new was needed for what the user sees: `HealthReply` already has a detail beside `ready` and
the overlay already renders it as `Brain ready: <line>`, so a serving report with something to say
takes the slot the version string held, with no proto, Rust or TypeScript change.

What this does not cover is a tier that dies without anybody having asked it to restart, measured
against a real sidecar the same day: a tier with a bad artifact answers `200 loading` to a `start`
and `failed` seconds later, so the restart loop marks it as running and nothing reports it. That is
the first of the three entries below.

## History

- 2026-07-18: Opened by the pass that made the drain window wait for the residency restore rather
  than for the enclosing `finally`.
- 2026-07-18: The model-host sub-slice made it reachable by configuration for the first time and cut
  its cost, since a spawn placed on a dead tier now re-runs once on the CPU rather than only
  reporting.
- 2026-07-18: The health-reporting sub-slice shipped and did not clear it, because the published
  `ResidencyReport` has no per-tier state for a placer to read.
- 2026-08-09: Closed ahead of its trigger. Its account of the code was checked first and held on
  three points (the restart really is best effort, `undrain` really does reopen on every path, and
  `ResidencyReport` really has no per-tier state) and moved on two. The failure side was witnessed
  against a real `model-host` container over real HTTP, both a tier the daemon refuses outright and
  one that accepts a start and dies, and three entries opened in its place.
