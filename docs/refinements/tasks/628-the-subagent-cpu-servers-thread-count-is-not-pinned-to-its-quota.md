# The subagent CPU server's thread count is not set from its quota

**Status:** done 2026-09-11
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

`docker/docker-compose.subagents.yml` started the shipped subagent server under `cpus: 4.0` and
passed no `--threads`, so the server ran one thread per hardware thread it saw, 24 on the box the
row was drawn on, inside a quota of four. The container's `cpu.stat` read the cgroup throttled in
14,308 of 14,520 periods under that configuration, and its decode rate was 0.43 to 0.54 tokens a
second against 11.9 to 12.4 with the count set to the quota. The four default-count runs of that row
published so far read 711 s, 718 s, 1560 s and 1837 s at one argv on one image, so a stock
deployment's CPU placement had a wall clock that depended on what the scheduler did with the quota
that day.

Setting `--threads` from the quota in the compose file is a default on the GPU box, so it was the
owner's to decide. Three questions about how to write it were open: `cpus:` takes the budget as the
brain prints it, a float, while `--threads` takes an integer, so the count could not be
`${CORTEX_SUBAGENTS_CPU_BUDGET}` unchanged once a deployment set a fractional budget;
`--threads-batch` defaults to `--threads`; and the roster alternate in
`docker-compose.subagents-roster.yml` had no quota at all
([R-616](616-the-roster-alternates-cpu-server-carries-neither-cgroup-cap.md)).

**What follows from it.** The injection harness's CPU placement starts a row with the tier's own
argv and the compose file's cgroup caps, so once the compose file has a thread count the CPU row
must use the same one from the same constant, or the row measures a configuration no deployment
runs. And the 0.18 to 1.35 tokens a second `docs/runbooks/subagents-cpu.md` recorded for the tier is
a range of the default-count configuration, an order of magnitude below the new one, so the
runbook's budgeting sentence and the stall and run ceilings sized from it had to be read again.

## History

- 2026-09-11: opened by the close of
  [R-627](627-the-cpu-rows-wall-clock-does-not-reproduce-the-published-one.md), which drew the
  subagent pick's CPU row once with `llama-server`'s default thread count and twice with
  `--threads 4` under the same four-CPU quota, and got 1560.15 s against 114.08 s and 114.86 s on
  counts that repeat cell for cell. The pair is published in the fixed-thread-count run of
  2026-09-11 (injection text rows readings); the compose file was left unchanged because its
  default is the owner's.
- 2026-09-11: read against
  [R-616](616-the-roster-alternates-cpu-server-carries-neither-cgroup-cap.md). The alternate ran
  the same 24 default threads with no quota to throttle against, so the factor of 13.7 was a cost
  only the capped server paid, and capping the alternate without setting its count would have given
  it that cost. The caps and the thread count therefore belonged in one change using one constant.
- 2026-09-11: done, with the default decided on the pair's evidence. The three questions above were
  settled by measurement. llama-server on build `b10680-d7bd3bfca` floors a float `--threads`,
  logging `n_threads = 4` for `4.0` and 2 for `2.5`, so both CPU servers pass
  `"${CORTEX_SUBAGENTS_CPU_BUDGET:-4.0}"` unchanged, the same substitution their `cpus` cap reads,
  and the constant scan needed only its counts raised (three in the subagents file, two in the
  roster file). `--threads 0.5` logged 24, the engine default, which is
  [R-636](636-a-cpu-budget-under-one-floors-the-thread-count-to-the-engines-default.md). No
  `--threads-batch` was added, the fixed-count server evaluating a prompt at 77.6 tok/s. The roster
  alternate got its caps in the same change, closing
  [R-616](616-the-roster-alternates-cpu-server-carries-neither-cgroup-cap.md). The harness's CPU row
  passes the same count through `Placement.threads`, from `DEFAULT_CPU_BUDGET`.
  `scripts/flagcheck.py` does not check the count, since its rule covers the hosted GPU tier, which
  has no per-tier quota, and the count's value is its own service's `cpus` substitution; a CPU
  server in a third compose file is therefore checked by neither scan, which is
  [R-638](638-a-cpu-subagent-server-in-a-third-compose-file-is-held-to-no-thread-count.md). The
  runbook's range was measured again on the compose stack's own server: 12.24 to 12.44 tok/s for one
  idle slot, inside the pair's 11.9 to 12.4 as expected, 8.53 to 9.23 per slot with two, and 4.89 to
  5.03 and 3.02 to 3.07 on a host saturated by one busy loop per hardware thread, so the range now
  reads 3.0 to 12.4. The stall, run and admission-wait ceilings were not re-sized, since they rest
  on whole-subtask readings of the default-count configuration this run did not redraw, which is
  [R-637](637-the-delegated-run-ceilings-were-sized-on-the-unpinned-cpu-tier.md). Recorded in the
  thread-count change of 2026-09-11 ([ADR-0004](../../adr/ADR-0004-model-lineup.md)), with both
  mutation tables.
