# The stall ceiling sits between two registered bounds and is itself registered nowhere

**Status:** done 2026-08-23
**Area:** repo-checks
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

`brain/packages/core/src/cortex_core/subagents.py` states the ordering three bounds stand in: "the
pool's 600 s stall ceiling and its 3600 s admission wait, so the three are ordered by the scope of
what they bound". The run deadline in the middle has been a registry entry since it was added; the
admission wait above it is one now; the ceiling under it is not, and it is the one the brain's own
boot-time check reads (`config_subagents.py`, the `run_timeout_s <= stall_timeout_s` check). So one
sentence contains two checked numbers and one free one, which is the shape a presence test reads as
correct while half a line is wrong.

It has no declaration to read. `stall_timeout_s: float = Field(default=600.0, gt=0)` is an indented
pydantic field (`brain/packages/orchestrator/src/cortex_orchestrator/config_subagents.py`), and
this scan's Python declaration form is anchored at column 0. Hoisting it to a module constant is
the remedy this survey has used a dozen times, and it is a change to the config module rather than
a registry row.

## History

- 2026-08-23: filed by the close of
  [R-393](393-the-admission-waits-default-is-tied-to-nothing.md), which registered the admission
  wait and left the third number in the same ordering sentence loose.
- 2026-08-23: closed as one entry in `scripts/subagentcouplings.py`, one declaration and four
  matches. Its own count was low, as it warned it might be. It names three places; the tree has
  four, the miss being [modules/brain-inference.md](../../modules/brain-inference.md)'s "600 s for
  the CPU pool". The hoist went elsewhere than proposed: into `config_subagents.py` beside
  `DEFAULT_MEM_BUDGET_GB`, which is a module constant there for the same reason, rather than into
  `cortex_core` beside the run deadline. The pure core never uses this number, and putting one
  there to suit a scan would mean changing the architecture to satisfy the check. Out because it
  states no number: the compose override's list of settings, which documents the environment
  variable and leaves the value to the brain. Out on the suite rule: the unit test checking the
  default. Five planted changes each exited 1 and each restoration returned the check to passing,
  with one control staying green, the resident tier's own `stall_timeout_s` under the same field
  name in `config.py`. One residue filed: the sentence claims the three bounds are ordered and the
  registry now covers three independent values
  ([R-407](407-three-held-bounds-and-an-unheld-ordering.md)).
