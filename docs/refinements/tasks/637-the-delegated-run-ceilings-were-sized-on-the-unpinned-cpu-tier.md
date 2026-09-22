# The delegated run ceilings were sized on the CPU tier's default thread count

**Status:** open, waiting for its trigger
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-19
**Trigger:** a delegated run on the CPU server that holds its admission for the whole stall ceiling
or the whole run deadline while a peer queues behind it, a spawn refused at the admission wait, or
any retune of `CORTEX_SUBAGENTS_STALL_TIMEOUT_S`, `CORTEX_SUBAGENTS_RUN_TIMEOUT_S` or
`CORTEX_SUBAGENTS_ADMISSION_WAIT_S`.

The stall ceiling (600 s), the run deadline (2400 s) and the admission wait each rest on
whole-subtask readings of the CPU tier: 623.8 s for the longest narrow subtask, 222.8 to 324.3 s
across a full batch on an idle box, 595.2 s for the longest hold, and 1736.6 s beside a saturated
host (ADR-0005 decision 7, ADR-0048, and the delegated-run-holds readings). Every one of those was
drawn with the server running one thread per hardware thread inside its quota. With the count set to
the quota, the same server decodes at 12.2 to 12.4 tok/s on one slot of an idle host and 3.0 to 3.1
per slot on a saturated one, against the 1.26 to 1.35 and 0.18 of those readings, so each bound is
now several times looser than its own derivation asked for. In decoded tokens the run deadline
admits at least 7200 on a saturated host, above both the 1024 token cap and the 4096 token per-slot
context, so the deadline no longer fires before the cap on a busy box.

**Why it is not acted on now.** A looser bound cuts nothing its derivation meant to allow, so the
cost is time on a failure only: a wedged or looping run holds its admission longer than a tighter
bound would let it. Re-sizing needs the whole-subtask shapes the generation-bounds readings measured
drawn again under the new count, which the change did not draw, since it measured decode rates and
not subtasks. Each of the three is also one setting for the whole roster and both placements rather
than a per-entry one, the run deadline by ADR-0048 decision 12 and the other two because
`SubagentRosterEntry` declares no bound at all, and a slower CPU than this box's is what they were
sized to cover.

**What would settle it.** The five subtask shapes of the generation-bounds readings and the full
batch drawn on the server with the count set, idle and saturated, with the three bounds recomputed
from them by the rules [ADR-0048](../../adr/ADR-0048-generation-bounds.md) wrote down.

## History

- 2026-09-11: opened by the close of
  [R-628](628-the-subagent-cpu-servers-thread-count-is-not-set-from-its-quota.md). The subagent
  runbook now says its whole-subtask readings predate the change.
- 2026-09-12: checked against the tree, and one place still using the older arithmetic was
  corrected. The three declarations are unchanged and unretuned: `DEFAULT_STALL_TIMEOUT_S` is 600.0
  in `cortex_orchestrator/config_subagents.py`, `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` 2400.0 in
  `cortex_core/subagents.py` and `DEFAULT_ADMISSION_WAIT_S` 7200.0 in `cortex_core/scheduler.py`,
  and no delegated run is recorded held for a whole ceiling. The comment over
  `DEFAULT_SUBAGENT_MAX_TOKENS` still said the deadline admits about 425 decoded tokens on a
  saturated host and about 3200 on an idle one, that the per-slot context is the looser of the two
  bounds above the cap, and that a busy box costs this tier a factor of seven. All three are older
  readings: the deadline admits at least 7200 saturated and about 20,000 to 30,000 idle, the 4096
  per-slot context is now the tighter, and the load factor is about four. The comment now says so.
- 2026-09-15: the three declarations are still unchanged, and the first whole-subtask wall clock
  under the new count is drawn. The delegated run that closed
  [R-629](629-the-picks-cpu-server-reaches-its-memory-cap-under-the-harnesss-budget.md) ran six
  attempts that each stopped at the 1024-token cap, which is a whole subtask of the shape this
  deadline bounds: 86.57 s and 86.79 s with one attempt decoding at a time, 122.89 s and 121.81 s
  with two at once, on prompts of about 100 tokens. On an idle host the deadline is about twenty
  times the longest of those, and about seven times the figure derived from the tier's published
  saturated rate. That is one shape of the five the original derivation measured and it is a capped
  attempt rather than a tool-using run, so no bound moves on it.
- 2026-09-17: took over the refused-spawn half of the trigger from the close of
  [R-430](430-the-bounds-are-sized-on-an-idle-box.md), which asked for the same measurement under
  load. A spawn refused at the admission wait can follow a queue of runs that each finished inside
  the deadline, so the half about one run holding its admission did not cover it.
- 2026-09-19: the three declarations are unchanged and unretuned, and a retune on the host now
  reaches the brain. `DEFAULT_STALL_TIMEOUT_S` is 600.0, `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` 2400.0 and
  `DEFAULT_ADMISSION_WAIT_S` 7200.0, no file that declares them has changed since the last reading,
  and no delegated run or refused spawn is recorded. Two things moved around it. Until 2026-09-17 no
  compose file named the three variables, so a value set on the host never reached the dockerized
  brain and the retune clause could fire only through the constants; the subagents overlay now
  passes all three by name, so a `.env` line is a retune this trigger counts. And the paragraph
  above said `SubagentRosterEntry` declares nothing beyond an endpoint, a GPU endpoint and three
  asks, when it has declared a `description` since before this entry was opened; what the argument
  needs is that it declares no bound, and the sentence now says that.
