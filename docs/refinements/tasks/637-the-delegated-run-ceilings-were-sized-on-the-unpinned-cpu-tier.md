# The delegated run ceilings were sized on the unpinned CPU tier

**Status:** open, fix when it bites
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** a delegated run on the pinned CPU server that holds its admission for the whole stall
ceiling or the whole run deadline while a peer queues behind it, or any retune of
`CORTEX_SUBAGENTS_STALL_TIMEOUT_S`, `CORTEX_SUBAGENTS_RUN_TIMEOUT_S` or
`CORTEX_SUBAGENTS_ADMISSION_WAIT_S`.

Opened 2026-09-11 by the close of
[R-628](628-the-subagent-cpu-servers-thread-count-is-not-pinned-to-its-quota.md), which pinned the
CPU subagent servers' thread count to their quota and re-measured the tier's decode band under it.

**What is known.** The stall ceiling (600 s), the run deadline (2400 s) and the admission wait each
rest on whole-subtask readings of the CPU tier: 623.8 s for the longest narrow subtask, 222.8 to
324.3 s across a full batch on an idle box, 595.2 s for the longest hold, and 1736.6 s beside a
saturated host (the ADR-0005 stall-ceiling, total-cap and batch addenda). Every one of those was
drawn with the server running one thread per hardware thread inside its quota. Pinned, the same
server decodes at 12.2 to 12.4 tok/s on one slot of an idle host and 3.0 to 3.1 a slot on a
saturated one, against the 1.26 to 1.35 and 0.18 of those readings, so each bound is now several
times looser than its own derivation asked for. In decoded tokens the run deadline admits at least
7200 on a saturated host, above both the 1024 token cap and the 4096 token per-slot context, so the
deadline no longer fires before the cap on a busy box.

**Why it is not acted on now.** A looser bound cuts nothing its derivation meant to allow, so the
cost is time on a failure only: a wedged or looping run holds its admission for longer than a
tighter bound would let it. Re-sizing needs the whole-subtask shapes those addenda measured drawn
again under the pinned count, which the close did not draw, since it measured decode rates and not
subtasks. The three bounds are also one pair for the whole roster and both placements by decision
(ADR-0005 roster-bounds addendum), and a slower CPU than this box's is what they were sized to
cover.

**What would settle it.** The ADR-0005 ceilings addendum's five subtask shapes and its full batch
drawn on the pinned server, idle and saturated, with the three bounds re-derived from them by the
rules those addenda wrote down.

## Trail

- 2026-09-11: opened by the close of
  [R-628](628-the-subagent-cpu-servers-thread-count-is-not-pinned-to-its-quota.md). The subagent
  runbook now says its whole-subtask readings predate the pin.
