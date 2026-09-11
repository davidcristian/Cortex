# The subagent CPU server's thread count is not pinned to its quota

**Status:** landed 2026-09-11
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
- 2026-09-11: the trigger sweep over the roster alternate's uncapped server, recorded in
  [R-616](616-the-roster-alternates-cpu-server-carries-neither-cgroup-cap.md), read the two
  entries against each other. The alternate runs the same unpinned 24 threads as the pick's
  server with no quota to throttle against, so the factor of 13.7 measured above is a cost only
  the capped server pays today, and capping the alternate without pinning its count would hand
  it that cost. The caps and the pin therefore belong in one change carrying one constant, the
  alternate's caps landing first or beside the pin; this entry's compose default stays the
  owner's.
- 2026-09-11: landed, with the default decided on the pair's evidence. The three spelling
  questions above were settled by measurement rather than by a rule. llama-server on build
  `b10680-d7bd3bfca` floors a float `--threads`, logging `n_threads = 4` for `4.0` and 2 for
  `2.5`, so both CPU servers pass `"${CORTEX_SUBAGENTS_CPU_BUDGET:-4.0}"` verbatim, the
  substitution their `cpus` cap reads, and the constant scan needed only its counts raised (three
  in the subagents file, two in the roster file) with no integer form to accept. `--threads 0.5`
  logged 24, the engine default, which is
  [R-636](636-a-cpu-budget-under-one-floors-the-thread-count-to-the-engines-default.md). No
  `--threads-batch` was added, the pinned server evaluating a prompt at 77.6 tok/s. The roster
  alternate got its caps in the same change, closing
  [R-616](616-the-roster-alternates-cpu-server-carries-neither-cgroup-cap.md). The harness's CPU
  row passes the same count through `Placement.threads`, from `DEFAULT_CPU_BUDGET`. The flag gate
  does not carry the count, since its rule covers the hosted GPU tier, which has no per-tier quota
  to pin to, and the count's value is its own service's `cpus` substitution; a CPU server in a
  third compose file is therefore held by neither scan, which is
  [R-638](638-a-cpu-subagent-server-in-a-third-compose-file-is-held-to-no-thread-count.md). The
  runbook's band was re-measured on the compose stack's own server: 12.24 to 12.44 tok/s for one
  idle slot, inside the pair's 11.9 to 12.4 as expected, 8.53 to 9.23 a slot with two, 4.89 to
  5.03 and 3.02 to 3.07 on a host saturated by one busy loop per hardware thread, so the band now
  reads 3.0 to 12.4. The stall, run and admission-wait ceilings were not re-sized, since they rest
  on whole-subtask readings of the unpinned shape this sitting did not redraw, which is
  [R-637](637-the-delegated-run-ceilings-were-sized-on-the-unpinned-cpu-tier.md). Recorded in the
  [ADR-0004 thread-pin landing addendum](../../adr/ADR-0004-model-lineup.md#addendum-2026-09-11-later-the-cpu-subagent-servers-thread-count-is-pinned-to-their-quota),
  with both mutation tables.
