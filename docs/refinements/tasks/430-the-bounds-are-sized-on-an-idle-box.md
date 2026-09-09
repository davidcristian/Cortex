# Every bound on a delegated run is sized on an idle box, and a busy one nearly reaches them

**Status:** open, fix when it bites
**Area:** resource-governance
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-09-09
**Trigger:** The first delegated run observed cut at its own deadline, or the first spawn refused
at the admission bound.

Opened 2026-08-25 by the close of [R-207](207-whole-subtask-figure-off.md), whose control run is
what says so.

Three bounds are multiples of "a whole CPU subtask on the shipped entry": the stall ceiling is
about twice one, the run deadline four times one, and the admission wait was derived by
multiplying one out into a queue. Every reading behind every one of them was taken on an otherwise
idle machine. Measured against a saturated one, the same subtask shape on the same container and
the same server took **1736.6 s** where it takes 222.8 to 324.3 s quiet, decoding at 0.18 tok/s
against 1.26 to 1.35 and prefilling at 6.7 tok/s against 20.6. The subagent server's compose `cpus`
limit, which defaults to the brain's own `CORTEX_SUBAGENTS_CPU_BUDGET` of 4.0, is a quota rather
than a reservation, and llama.cpp starts a thread per host core rather than per quota core, so a
busy host costs this tier most of what it had rather than a fair share.

What that leaves is a **28% margin**: a legitimate narrow subtask on a busy box comes that close to
the 2400 s run deadline whose whole job is to cut a model that will not stop. Past it, the refusal
tells the cortex to narrow a subtask that was never the problem, and it skips the CPU re-run,
truncations being deliberately never re-placed. A full batch on such a box is worse: its last
spawn would queue past even the raised 7200 s admission wait, and be refused under a message about
a queue that was draining exactly as fast as the machine allowed.

**Why it was left.** The arm that produced these numbers is a shell loop spawning a process per
iteration, so it loads the kernel as well as the cores. It is honest about direction and order of
magnitude and useless as a calibration, and a bound raised on it would be a bound sized on a shell
loop. The measurement that would settle it is a real one: the shipped stack up, the cortex
resident and generating, the tools sidecars running, and a delegated batch measured against that
rather than against an idle box.

**The second of the two answers this entry offered is already written**, so what is left is the
first. The delegation runbook now states in three places that every number in it is an idle-box
number: beside the stall ceiling, where it gives the saturated arm's 1736.6 s next to the idle
222.8 to 324.3 s and says the ceiling is comfortable either way; beside the cap, where it converts
the deadline into about 425 decoded tokens on a saturated host against about 3200 on an idle one
and says that raising the cap on a busy box buys nothing; and under the ceilings table, where it
names 1736.6 s against the 2400 s deadline and sends the reader here
([runbooks/subagents-cpu.md](../../runbooks/subagents-cpu.md)). A reader who hits the refusal is
therefore told what happened. The bounds are unchanged and unmeasured under load.

**What would close it.** Take the measurement, and then decide whether the bounds move. Moving them
means the run deadline first and the admission wait behind it, since the wait is held at three
deadlines and the pair fails validation at boot if it is not. A second option worth pricing while
the numbers are in hand is pinning the tier's thread count to its quota (`--threads` alongside the
compose `cpus` limit), since oversubscribing 24 threads onto a 4 CPU quota is part of what the
control measured and is a compose line rather than a bound.

## Trail

- 2026-08-25: opened by the close of [R-207](207-whole-subtask-figure-off.md), whose batch
  measurement confirmed both bounds on an idle box and whose control run then showed the same
  subtask taking five to eight times longer on a saturated one.
- 2026-09-09: **Held to the tree. The three bounds are still the shipped ones and nothing has
  measured them under load, but one of the two answers this entry offered had been taken before it
  was written.** `DEFAULT_STALL_TIMEOUT_S` is 600.0 in
  `cortex_orchestrator/config_subagents.py`, `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` 2400.0 and
  `DEFAULT_ADMISSION_WAIT_S` 7200.0 in `cortex_core`, and no delegated run is recorded cut at its
  own deadline: the one measured run that did not finish, the open-ended essay at 577 tokens and
  1958 s, was stopped because the measurement ended. The runbook's idle-box warnings are what the
  body above now names, so the entry asks for the measurement alone. Two smaller repairs: the tier's
  CPU quota is a compose `cpus` limit defaulting off `CORTEX_SUBAGENTS_CPU_BUDGET` rather than a
  `--cpus 4.0` literal, and `--threads` is still on no subagent server's argv.
