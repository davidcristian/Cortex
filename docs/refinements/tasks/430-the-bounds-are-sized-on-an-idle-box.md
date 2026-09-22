# Every bound on a delegated run was sized on an idle box, and a busy one nearly reaches them

**Status:** satisfied 2026-09-17
**Area:** resource-governance
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)

Three bounds are multiples of a whole CPU subtask on the shipped tier: the stall ceiling is about
twice one, the run deadline four times one, and the admission wait was derived by multiplying one
out into a queue. Every reading behind all three was taken on an otherwise idle machine. Measured
against a saturated one, the same subtask shape on the same container and the same server took
1736.6 s where it takes 222.8 to 324.3 s when quiet, decoding at 0.18 tok/s against 1.26 to 1.35
and prefilling at 6.7 tok/s against 20.6. The subagent server's compose `cpus` limit, which
defaults to the brain's own `CORTEX_SUBAGENTS_CPU_BUDGET` of 4.0, is a quota rather than a
reservation, and llama.cpp starts a thread per host core rather than per quota core, so a busy host
costs this tier most of what it had.

That leaves a 28% margin: a legitimate narrow subtask on a busy box comes that close to the 2400 s
run deadline whose job is to cut a model that will not stop. Past it, the refusal tells the cortex
to narrow a subtask that was never the problem, and it skips the CPU re-run, truncations being
deliberately never re-placed. A full batch on such a box is worse: its last spawn would queue past
even the raised 7200 s admission wait.

The measurement that produced these numbers was a shell loop spawning a process per iteration, so
it loads the kernel as well as the cores. It is accurate about direction and order of magnitude and
useless as a calibration. What would settle it is the shipped stack up, the cortex resident and
generating, the tools sidecars running, and a delegated batch measured against that.

The documentation half is already done. The delegation runbook states in three places that every
number in it is an idle-box number, so a reader who hits the refusal is told what happened
([runbooks/subagents-cpu.md](../../runbooks/subagents-cpu.md)). The bounds themselves were
unchanged and unmeasured under load.

## History

- 2026-08-25: opened by the close of [R-207](207-whole-subtask-figure-off.md), whose batch
  measurement confirmed both bounds on an idle box and whose control run then showed the same
  subtask taking five to eight times longer on a saturated one.
- 2026-09-09: checked against the tree. The three bounds are still the shipped ones and nothing had
  measured them under load, but one of the two answers this entry offered had been taken before it
  was written. `DEFAULT_STALL_TIMEOUT_S` is 600.0 in `cortex_orchestrator/config_subagents.py`,
  `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` 2400.0 and `DEFAULT_ADMISSION_WAIT_S` 7200.0 in `cortex_core`,
  and no delegated run is recorded cut at its own deadline: the one measured run that did not
  finish, the open-ended essay at 577 tokens and 1958 s, was stopped because the measurement ended.
  Two smaller repairs: the tier's CPU quota is a compose `cpus` limit defaulting off
  `CORTEX_SUBAGENTS_CPU_BUDGET` rather than a `--cpus 4.0` literal, and `--threads` was still on no
  subagent server's argv.
- 2026-09-17: satisfied, because the saturated reading this entry rests on was taken on a server
  configuration the stack no longer starts. The 1736.6 s subtask and its 0.18 tok/s decode were
  taken with the CPU server running 24 threads inside a 4 CPU quota. On 2026-09-11 the close of
  [R-628](628-the-subagent-cpu-servers-thread-count-is-not-set-from-its-quota.md) took the second
  answer this entry offered: both CPU subagent servers in `docker/docker-compose.subagents.yml` and
  `docker/docker-compose.subagents-roster.yml` now pass `--threads` from the same
  `CORTEX_SUBAGENTS_CPU_BUDGET` substitution as their `cpus` cap. The same close took the first
  answer, a reading under load: on the fixed server a saturated host decodes 4.89 to 5.03 tok/s on
  one slot and 3.02 to 3.07 on each of two, against 12.24 to 12.44 idle, so load costs one slot a
  factor of about 2.5 where the unfixed server lost a factor of seven. It then decided the bounds
  do not move. At the slower of those rates the 2400 s deadline admits at least 7200 decoded
  tokens, seven times the 1024 token cap, so the 28% margin above no longer describes the shipped
  stack, and the batch reading behind `DEFAULT_ADMISSION_WAIT_S` (the eighth spawn admitted
  1624.6 s in, serial, idle, unfixed) sits under the 7200 s wait at the fixed saturated rates too,
  those being faster than the unfixed idle 1.26 to 1.35 tok/s. That last comparison is a ratio of
  decode rates and not a measured batch. The three declarations are unchanged, and no delegated run
  is recorded cut at its deadline or refused at the admission wait. What is left is measuring the
  whole-subtask shapes and a full batch on the fixed server, idle and saturated, which is
  [R-637](637-the-delegated-run-ceilings-were-sized-on-the-unpinned-cpu-tier.md) word for word; its
  trigger now also has this entry's refused-spawn half. The runbook paragraph that sent a reader
  here was restated on the fixed rates.
