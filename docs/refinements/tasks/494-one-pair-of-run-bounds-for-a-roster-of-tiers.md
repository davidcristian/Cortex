# One pair of run bounds reaches every roster entry and the entries convert between them differently

**Status:** open, fix when it bites
**Area:** subagents
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** the first roster entry measured decoding materially apart from the default's 0.18 to
1.35 tok/s, which is either the GPU-placed subagent bring-up H-022 or an alternate faster than the
pick, since that is when one shared pair starts binding at a different end for different entries.

Opened 2026-08-29 by the close of
[R-478](478-two-ceilings-on-one-run-and-no-ordering.md), whose decision is that the cap and the run
deadline are independent bounds and that converting between them is the operator's own work, done
at the tier's decode rate.

That decision hands the operator a conversion that is **per tier**, and the config gives them one
pair of numbers for the whole roster. `SubagentsConfig.attempt_bounds` builds a single
`AttemptBounds` from the flat `max_tokens` and `run_timeout_s`; `build_subagents` hands that one
value to the one `SubagentRunner`, which holds one `PlacedAttempt`, so every entry runs under it.
`SubagentRosterEntry` carries an endpoint, a GPU endpoint, the three resource asks and a
description, and no bounds at all, though the asks are the precedent for adding some: each defaults
off the flat field's own module constant. The rates those bounds convert at are already not one
number across the entries this repo ships. The delegation runbook reads gemma-4-E4B at 0.18 to 1.35
tok/s and Qwen3.5-2B at about 1 tok/s, and a GPU placement is a different number again on both.

**Why it was left.** Nothing shipped is hurt yet, and the reason is that the measured rates
overlap: the roster alternate's roughly 1 tok/s sits inside the default entry's own interval, so one
pair covers both about as well as it covers either. The cost is also not the two JSON fields it
looks like. Three boot checks are written against **one** deadline, and each would have to become a
check per entry: the deadline against the stall ceiling, which is one ceiling because every entry
shares one generation client; the hold against the admission wait, which is one wait because every
entry queues on one `ResourceBudgetScheduler`; and the deadline against a whole delegated dispatch,
which is one tool configuration. Per-entry deadlines would make the second of those a relation
between one entry's hold and a wait every other entry is queued behind, which is a different and
harder claim than the one that check makes today. This is the same shape as
[R-482](482-the-sentence-is-one-wording-for-every-entry.md), one flat setting applied to a roster
whose entries do not agree about it, and the two would be worth reading together.

**What would close it.** Measure a second entry's decode rate against the default's, on the same
bodies and the same shapes the ceilings table was read on, and the GPU placement with it
([H-022](../../host/tasks/022-gpu-placed-subagent.md), which is the reading furthest from the
default's), and then take one of two answers. If the
rates really are far apart, put `max_tokens` and `run_timeout_s` on `SubagentRosterEntry`
defaulting off the flat fields the way the resource asks already do, and decide what the three
orderings compare when a roster has several deadlines: most likely the longest, since the wait and
the dispatch bound are pool-wide. If they are not far apart, say so where the roster is documented,
so the next reader of the independence decision knows the conversion is one tier's on purpose
rather than by omission.

## Trail

- 2026-08-29: opened by the close of
  [R-478](478-two-ceilings-on-one-run-and-no-ordering.md), which declared the cap and the run
  deadline independent and left the conversion between them to the operator, at a decode rate that
  is the entry's own while the pair of bounds is the deployment's.
