# An effort set on a template that reads none is logged at INFO

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)
**Verified:** 2026-11-21

The backend logs `reasoning effort not sent because the served template does not read it` at
`INFO` for every level (`cortex_inference/backend.py`, ADR-0049 decision 19). The level is `INFO`
because the default names `medium` on every deep tier, and a deep tier on a gemma file reads no
level. A deployment that sets `CORTEX_REASONING_EFFORT_BRAIN` to `low` or `high` on such a tier
gets the same `INFO` line, although the setting it wrote does nothing there. The adapter reads
only `GenerationBounds.effort`, which does not say whether the deployment wrote the level.

## Proposal

Log the line at `WARNING` when the deployment wrote the level and at `INFO` when it is the
default. The brain's configuration is the one place that has both facts, so the check is either
made there at boot, against the deep server's first `/props` answer, or the bounds say which case
they are. The safe direction is `INFO`: a warning on every start of a default deployment is the
fault the present level avoids.

**What closes it.** The two levels with their tests and decision 19 stating them, or a decline
recorded here.

## History

- 2026-11-21: filed when `medium` became the default level and the line was lowered from
  `WARNING` ([R-738](738-the-deep-tier-cannot-set-a-templates-reasoning-effort-or-preserve-flag.md)).
