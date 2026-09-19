# A CPU budget under one makes the thread count fall back to the engine's default

**Status:** open, waiting for its trigger
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-19
**Trigger:** a deployment that sets `CORTEX_SUBAGENTS_CPU_BUDGET` below 1.0, or a brain config
change that lets the budget reach a CPU subagent server by any route other than the compose
substitution both CPU servers read.

llama-server on build `b10680-d7bd3bfca` reads `--threads` with an integer parse that stops at the
point, so `--threads 4.0` starts `n_threads = 4` and `--threads 2.5` starts `n_threads = 2`, which
is why the budget can be passed unchanged. `--threads 0.5` parses to 0, and the engine takes a count
of 0 or below as its own default of one thread per hardware thread: the server logged
`n_threads = 24` under `--cpus 4.0` on the 24-thread box. So a budget under one CPU starts the
configuration the explicit count exists to prevent, the one measured at 1560 s against 114 s on the
pick's CPU row. `SubagentsConfig.cpu_budget` is `Field(gt=0)`, so the brain accepts such a budget,
and its admission-wall validator only asks that every entry's `cpus` ask fit under it.

**Why it is not acted on now.** No deployment of this stack runs a subagent server on less than one
CPU, and the shipped asks are 2.0 for both entries, so a budget under one already fails the brain at
boot unless every ask is lowered with it. Two fixes exist and neither is free: a boot rule in the
brain refusing a budget under 1.0, which puts a fact about one engine's argument parser into the
brain's config, or a compose form that rounds up, which compose substitution cannot express.

**Reaching it takes two deliberate changes, and one of them is loud.** The compose file passes the
same substitution to the brain and to both containers, so `CORTEX_SUBAGENTS_CPU_BUDGET=0.5` starts
each llama-server at 24 threads inside half a CPU and fails the brain at boot on the admission wall,
which compares each entry's `cpus` ask of 2.0 against the whole budget. The stack is then down at
the brain, with a server nothing calls. For the fallback count to serve a spawn, the same change
must lower every ask to at or under the budget as well.

## History

- 2026-09-11: opened by the close of
  [R-628](628-the-subagent-cpu-servers-thread-count-is-not-pinned-to-its-quota.md), from three
  containers started with `--threads 4.0`, `2.5` and `0.5` under `--cpus 4.0` and read back by the
  server's own `llama threadpool init` line.
- 2026-09-12: checked against the tree. The entry's account of the brain is right and its trigger
  was wider than the defect. `DEFAULT_CPU_BUDGET` is 4.0 and `cpu_budget` is
  `Field(default=DEFAULT_CPU_BUDGET, gt=0)` in `config_subagents.py`, so any positive budget is
  accepted; `_every_ask_must_fit_the_whole_budget` compares each entry's `cpus` and `memory_gb`
  against the whole budget and nothing else, and `DEFAULT_CPUS` is 2.0 with the roster override's
  JSON value 2.0 again. Both CPU servers still read `"${CORTEX_SUBAGENTS_CPU_BUDGET:-4.0}"` for
  `--threads` and for `cpus`, and no other route reaches a server, so neither half of the trigger
  has fired. The paragraph above about the two changes was added here.
- 2026-09-15: run whole for the first time, and the claim holds with the quota included. The reading
  that opened this entry passed `--threads 0.5` to a container under a four-CPU quota, which reads
  the engine's parse and not what a budget of 0.5 starts. Run as that budget would start it,
  `--cpus 0.5 --memory 8g --memory-swap 8g --threads 0.5` on the shipped argv and artifact and the
  same image and build, `docker inspect` gave 500,000,000 nanocpus and the server logged
  `llama threadpool init, n_threads = 24`. Published in the delegated-memory reading of 2026-09-15
  ([model lineup](../../readings/model-lineup.md)).
- 2026-09-19: checked again, and neither half of the trigger has fired. `DEFAULT_CPU_BUDGET` is
  still 4.0 and `cpu_budget` still `Field(default=DEFAULT_CPU_BUDGET, gt=0)`, and
  `_every_ask_must_fit_the_whole_budget` still compares each entry's asks against the whole budget
  and nothing else. Both CPU servers still pass `"${CORTEX_SUBAGENTS_CPU_BUDGET:-4.0}"` to
  `--threads` and to `cpus`, in `docker/docker-compose.subagents.yml` and
  `docker/docker-compose.subagents-roster.yml`, and the model host builds no argv from the budget.
  The 2026-09-17 pass-through of the brain's settings by name left this variable as it was.
