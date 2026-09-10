# The subagent CPU server's thread count is not pinned to its quota

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

Opened 2026-09-11 by the close of
[R-627](627-the-cpu-rows-wall-clock-does-not-reproduce-the-published-one.md), which drew the
subagent pick's CPU row once with `llama-server`'s default thread count and twice with `--threads 4`
under the same four-CPU quota, and got 1560.15 s against 114.08 s and 114.86 s on counts that
replicate cell for cell.

**What is known.** `docker/docker-compose.subagents.yml` starts the shipped subagent server under
`cpus: 4.0` and passes no `--threads`, so the server runs one thread per hardware thread it sees, 24
on the box the row was drawn on, inside a quota of four. The container's `cpu.stat` read the cgroup
throttled in 14,308 of 14,520 periods under that shape, and its decode rate was 0.43 to 0.54 tokens
a second against 11.9 to 12.4 with the count pinned to the quota. The four unpinned sittings of that
row published so far read 711 s, 718 s, 1560 s and 1837 s at one argv on one image, so the shape
a stock deployment runs its CPU placement at has a wall clock that depends on what the scheduler
does with the quota that day.

**The decision, and whose it is.** Pinning `--threads` to the quota in the compose file is a default
on the GPU box and is the owner's to set. The recommendation from the pair is to pin it. Three
things about the spelling are the entry's to settle when it lands. `cpus:` takes the budget as the
brain prints it, a float, and `--threads` takes an integer, so the count cannot be
`${CORTEX_SUBAGENTS_CPU_BUDGET}` verbatim once a deployment sets a fractional budget; the constant
scan holds every spelling of that budget in this file to `DEFAULT_CPU_BUDGET` and would need to
accept the integer form, as `defaultcheck.py` accepts a re-spelled default by value.
`--threads-batch` defaults to `--threads`, and the pair measured prompt processing at 66 to 71
tokens a second at the pinned count, so no second flag is owed unless a later reading says
otherwise. And the roster alternate in `docker-compose.subagents-roster.yml` carries no quota at all
([R-616](616-the-roster-alternates-cpu-server-carries-neither-cgroup-cap.md)), so a pinned count
there has no quota to be pinned to until that entry lands.

**What follows from the pin.** The injection harness's CPU placement starts a row with the tier's
own argv and the compose file's cgroup caps, so once the compose file carries a thread count the CPU
row should carry the same one, read off the same constant, or the row measures a shape no deployment
runs again. `scripts/flagcheck.py` derives the set of subagent servers the stack starts and holds
each to the flags its tier requires, which is where a pinned count would be held. And the 0.18 to
1.35 tokens a second `docs/runbooks/subagents-cpu.md` records for the tier under its cap is a band
of the unpinned shape, which the pinned one sits an order of magnitude above, so the runbook's
budgeting sentence and the stall and run ceilings sized from it are re-read once the count is
pinned.

**What would close it.** The owner's decision on the compose default; then the flag in the compose
file, the harness's CPU row and the flag gate carrying the same count from one constant, and the
runbook's band re-measured under it.

## Trail

- 2026-09-11: opened by the close of
  [R-627](627-the-cpu-rows-wall-clock-does-not-reproduce-the-published-one.md). The pair that entry
  asked for is published in the origin record's pinned-thread addendum; the compose file is
  unchanged because its default is the owner's.
