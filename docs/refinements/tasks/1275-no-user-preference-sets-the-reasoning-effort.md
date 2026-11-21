# No user preference sets the reasoning effort

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)
**Trigger:** a History line in this file recording the maintainer's pick of the three level names and the key.
**Verified:** 2026-11-21

The deep reply names one reasoning effort on every turn: `medium`, unless the deployment's
`CORTEX_REASONING_EFFORT_BRAIN` names another level or is empty (ADR-0049 decision 20). The person
using the assistant cannot change it. No preference key holds a level, and no code under
`brain/packages`, `body` or `proto` names `reply.effort`.

## Proposal

One user preference. One level for every turn, written with `SetPreference` and read by the brain,
which changes ADR-0032's rule that the brain never parses a preference, and hidden where the
serving model has no effort setting, which today is every pick but the deep one. It is not a
per-message control, because the deep handoff's confirm card already asks mid-turn whether to
think harder. Names await the maintainer's pick: **Wade, Swim, Dive** (recommended; the overlay's
surfaces are water already), or Stroll, Hike, Trek, or Presto, Andante, Largo; key `reply.effort`.

**What closes it.** The preference built behind its port under the picked names, or a decline
recorded here.

## History

- 2026-11-21: moved here from
  [R-738](738-the-deep-tier-cannot-set-a-templates-reasoning-effort-or-preserve-flag.md),
  whose first step, the deployment's default level, is built. It was that task's optional second
  step, and nothing of it is built.
