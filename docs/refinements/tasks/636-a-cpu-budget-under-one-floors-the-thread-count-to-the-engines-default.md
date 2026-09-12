# A CPU budget under one floors the thread count to the engine's default

**Status:** open, fix when it bites
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-12
**Trigger:** a deployment that sets `CORTEX_SUBAGENTS_CPU_BUDGET` below 1.0, or a brain config
change that lets the budget reach a CPU subagent server by any other spelling than the compose
substitution both CPU servers read.

Opened 2026-09-11 by the close of
[R-628](628-the-subagent-cpu-servers-thread-count-is-not-pinned-to-its-quota.md), which pinned both
CPU subagent servers' `--threads` to the substitution their `cpus` cap reads.

**What is known.** llama-server on build `b10680-d7bd3bfca` reads `--threads` with an integer parse
that stops at the point, so `--threads 4.0` starts `n_threads = 4` and `--threads 2.5` starts
`n_threads = 2`, which is why the budget can be passed verbatim. `--threads 0.5` parses to 0, and
the engine takes a count of 0 or below as its own default of one thread per hardware thread: the
server logged `n_threads = 24` under `--cpus 4.0` on the 24-thread box. So a budget under one CPU
starts the unpinned shape the pin exists to prevent, the one measured at 1560 s against 114 s on the
pick's CPU row. `SubagentsConfig.cpu_budget` is `Field(gt=0)`, so the brain accepts such a budget,
and its admission-wall validator only asks that every entry's `cpus` ask fit under it.

**Why it is not acted on now.** No deployment of this stack runs a subagent server on less than one
CPU, and the shipped asks are 2.0 for both entries, so a budget under one already fails the brain at
boot unless every ask is lowered with it. Two remedies exist and neither is free: a boot rule in
the brain refusing a budget under 1.0, which puts a fact about one engine's argument parser into the
brain's config, or a compose spelling that rounds up, which compose substitution cannot express.

**The door is narrower than the trigger reads, and what comes through it is loud.** Lowering the
budget alone does not reach a dialed server. The compose file passes the same substitution to the
brain and to both containers, so `CORTEX_SUBAGENTS_CPU_BUDGET=0.5` starts each llama-server at 24
threads inside half a CPU and fails the brain at boot on the admission wall, which compares each
entry's `cpus` ask of 2.0 against the whole budget. The stack is then down at the brain, with a
server nothing dials. For the floored count to serve a spawn, the same step must lower every ask to
at or under the budget as well, which is two deliberate retunes rather than one. That is what makes
this fix-when-it-bites rather than actionable: the single-knob version of it announces itself.

## Trail

- 2026-09-11: opened by the close of
  [R-628](628-the-subagent-cpu-servers-thread-count-is-not-pinned-to-its-quota.md), from three
  containers started with `--threads 4.0`, `2.5` and `0.5` under `--cpus 4.0` and read back by the
  server's own `llama threadpool init` line.
- 2026-09-12: **held to the tree, and the entry's own account of the brain is right while its
  trigger is wider than the defect.** `DEFAULT_CPU_BUDGET` is 4.0 and `cpu_budget` is
  `Field(default=DEFAULT_CPU_BUDGET, gt=0)` in `config_subagents.py`, so any positive budget is
  accepted; `_every_ask_must_fit_the_whole_budget` compares each entry's `cpus` and `memory_gb`
  against the whole budget and nothing else, and `DEFAULT_CPUS` is 2.0 with the roster override's
  JSON spelling 2.0 again. Both CPU servers still read `"${CORTEX_SUBAGENTS_CPU_BUDGET:-4.0}"` for
  `--threads` and for `cpus`, and no other spelling of the budget reaches a server, so neither half
  of the trigger has fired. What the re-derivation adds is the paragraph above: the budget alone
  cannot reach a running server, because the brain refuses to start on the same value, so this
  needs the asks lowered in the same step. The thread flag's name is now held by the constant scan
  as well, which changes nothing here, the hole being the value's range rather than the flag.
