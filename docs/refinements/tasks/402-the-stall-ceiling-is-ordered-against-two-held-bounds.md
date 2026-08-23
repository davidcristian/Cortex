# The stall ceiling sits between two held bounds and is itself tied to nothing

**Status:** landed 2026-08-23
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-23 by the close of
[R-393](393-the-admission-waits-default-is-tied-to-nothing.md), which registered the admission wait
and left the third number in the same ordering loose.

`brain/packages/core/src/cortex_core/subagents.py` states the ordering three bounds stand in: "the
pool's 600 s stall ceiling and its 3600 s admission wait, so the three are ordered by the scope of
what they bound". The run deadline in the middle has been a registry entry since it landed; the
admission wait above it is one now; the ceiling under it is not, and it is the one the brain
actually refuses to boot against (`config_subagents.py`, the `run_timeout_s <= stall_timeout_s`
check). So one sentence now carries two held numbers and one free one, which is the shape a
presence check reads as green while half a line is wrong.

**Why it was left.** It has no declaration to read.
`stall_timeout_s: float = Field(default=600.0, gt=0)` is an indented pydantic field
(`brain/packages/orchestrator/src/cortex_orchestrator/config_subagents.py`), and this scan's Python
declaration form is anchored at column 0. Hoisting it to a module constant is the remedy the
compose survey has paid a dozen times and the one the deadline beside it already lives under, but
it is a change to the config module rather than a registry row, and making it inside a close about
the wait would have hidden a code change under a taxonomy decision.

**What would close it.** Hoist the default to a constant beside the deadline it is ordered against,
then register the places that state it. Re-derive them rather than trusting this list: the ordering
comment above, [modules/brain-orchestrator.md](../../modules/brain-orchestrator.md)'s
`stall_timeout_s: float = 600.0`, and the delegation runbook's env paragraph are what a first
reading finds, and every entry in this area for the last day has been low. Note that the resident
tier has its own `stall_timeout_s`, defaulting to 120.0 in `config.py`, so a survey by number will
find two constants that are not the same value and one env name that is not this one.

## Trail

- 2026-08-23: filed by the close of
  [R-393](393-the-admission-waits-default-is-tied-to-nothing.md), which registered the admission
  wait and left the third number in the same ordering sentence loose.
- 2026-08-23: landed as one entry in `scripts/subagentcouplings.py`, one site and four mentions.
  **Its own count was low, as it warned it might be.** It names three far sides; the tree carries
  four, the miss being [modules/brain-inference.md](../../modules/brain-inference.md)'s "600 s for
  the CPU pool". **And the hoist went elsewhere than it proposed**: not into `cortex_core` beside
  the run deadline, but into `config_subagents.py` beside `DEFAULT_MEM_BUDGET_GB`, which is a
  module constant there for this same reason already. The pure core never spends this number, and
  putting one there to suit a scan would be the gate editing the architecture. Out because it
  states no number: the compose override's knob list, which documents the env var and leaves the
  value to the brain. Out on the suite rule: the unit test asserting the default. Five planted
  drifts each exited 1 and each restoration returned the gate to green, with one control staying
  green, the resident tier's own `stall_timeout_s` under the same field name in `config.py`;
  tabled in the ADR-0029 stall-ceiling addendum. One residue filed: the sentence claims the three
  bounds are ordered and the registry now holds three independent values
  ([R-407](407-three-held-bounds-and-an-unheld-ordering.md)).
