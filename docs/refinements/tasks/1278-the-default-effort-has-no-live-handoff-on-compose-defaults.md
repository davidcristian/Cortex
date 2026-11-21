# The default effort has no live handoff on compose defaults

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)
**Verified:** 2026-11-21

`CORTEX_REASONING_EFFORT_BRAIN` defaults to `medium`, and an empty value names no level (ADR-0049
decision 20). The one live handoff that sent `medium` had the variable written as `medium` in the
brain's environment
([readings](../../readings/model-swap.md#a-handoff-on-the-deep-pick)). No handoff has run with
the variable unset, where the level comes from the settings class, or with it empty.

What is checked: unit tests read the setting both ways, and `docker compose config` over the
repo's compose files (Compose v5.7.0) renders the unset variable as `null`, which never enters
the container, and the empty one as `""`. No brain container has been started either way.

## What to run

The three-turn chat with one handoff of the handoff reading, on the deep pick with its draft
layer and every other setting on its compose default, twice: once with the variable unset and
once with it empty. Expected, written here before either run:

- Unset: the brain reads the deep server's `/props` once, logs `reasoning effort sent` with
  `sent_as` `medium`, and the deep request has 861 prompt tokens.
- Empty: the brain logs no line about an effort and reads no `/props`, and the deep request has
  899 prompt tokens.
- Both runs pass every item of the handoff reading.

The driver of the two earlier runs is `run.sh` in `~/.cache/cortex-run/2026-11-21/b1/`.

**What closes it.** The two runs in the handoff reading, or the defect they show.

## History

- 2026-11-21: filed when `medium` became the default
  ([R-738](738-the-deep-tier-cannot-set-a-templates-reasoning-effort-or-preserve-flag.md)).
