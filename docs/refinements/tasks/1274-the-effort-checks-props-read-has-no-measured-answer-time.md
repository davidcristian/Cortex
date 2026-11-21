# The effort check's props read has no measured answer time

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)
**Verified:** 2026-11-21

A request that names a reasoning effort reads `GET /props` of the leased server inside the lease,
under `EFFORT_PROBE_TIMEOUT_S`, 2.0 s (`effort_probe.py`, ADR-0049 decision 18). The bound is the
one the system message probe has, whose worst answer was measured over 240 probes on four servers
(ADR-0071 decision 3). No reading says how long `/props` takes on the deep server. Its body holds
the whole chat template, and the read runs before every completion of a deep phase's tool loop.

The one live read, on Qwen3.8-27B with its draft layer on build b12375, was answered, and the
completion's headers arrived 0.0025 of that bound after the answer
([readings](../../readings/model-swap.md#a-handoff-on-the-deep-pick)). That says nothing about how
long the read itself took.

## Proposal

Read `/props` 240 times on the deep server as the model host starts it, idle and beside a
generation on its one slot, through the adapter's client and timeout. Write the worst answer, as a
share of the 2.0 s bound, into the readings and beside the constant. A worst answer above 0.25 of
the bound is a reason to ask once for each model process and not before every request, which
ADR-0049 decision 18 would then state.

**What closes it.** The readings row and the constant's comment, or the changed check.

## History

- 2026-11-21: filed when the effort check was built
  ([R-738](738-the-deep-tier-cannot-set-a-templates-reasoning-effort-or-preserve-flag.md)).
- 2026-11-21: `medium` became the deep tier's default effort, so every deep completion of a
  default deployment makes this read, and not only one whose deployment wrote a level.
