# Nothing counts how often the CPU re-run happens, so the doubled hold is sized from reasoning

**Status:** open, waiting for its trigger
**Area:** subagents
**Origin:** [ADR-0047](../../adr/ADR-0047-delegated-run-bound-ordering.md)
**Trigger:** a deployment recorded refused at the admission bound, which is the runner's `a spawn
was refused before it ran` warning, or a retune of the run deadline or the admission wait. In the
tree a retune is a move of `DEFAULT_ADMISSION_WAIT_S` (7200.0, `cortex_core/scheduler.py`),
`DEFAULT_SUBAGENT_RUN_TIMEOUT_S` (2400.0) or `ATTEMPTS_PER_ADMISSION` (2, both in
`cortex_core/subagents.py`), or a compose file giving `CORTEX_SUBAGENTS_ADMISSION_WAIT_S` or
`CORTEX_SUBAGENTS_RUN_TIMEOUT_S` a value, counted by
`grep -rnE 'CORTEX_SUBAGENTS_(ADMISSION_WAIT|RUN_TIMEOUT)_S: *[^ ]' docker/`. A value set only in a
host's shell or `.env` reaches the brain as well and is outside the tree.
**Verified:** 2026-09-24

`SubagentRunner._placed` logs a warning when a GPU-placed attempt is re-run on the CPU, and that is
the only trace the path leaves. Nothing counts the warnings, nothing passes the re-run into the
result the cortex reads except as a sentence inside `detail`, and no metric says what fraction of
spawns take two attempts. So the bound that now sits above two whole deadlines is sized against a
path whose real frequency nobody knows: the close that raised it worked the window out from reading
`_placed`, `PlacedAttempt.run` and the adapter's error translation, not from a deployment.

That mattered once already. The entry this closes narrowed its own window on 2026-08-23 by
reasoning about which branch a stalled stream reaches, got the branch wrong, and therefore got the
window wrong in the safe-sounding direction.

Counting is not free of design. The runner writes structured log records with the dispatch stamp's
vocabulary, and a count needs somewhere to live that survives a restart, which is a store rather
than a logger, so it is a port question. A bare counter in the runner would be process-local state
on an object whose whole contract is that it holds none between calls. The three workable shapes are
a field on the persisted `SubagentResult`, a Redis counter beside the `TaskStore`, or a log record
shaped for grepping and nothing more. Whichever is chosen, the number to write down is the
fraction, because the bound is sized against how often a peer is queued behind a re-run rather than
against whether the path happens at all.

## History

- 2026-08-25: opened by the close of
  [R-392](392-a-re-runs-second-deadline-outlasts-the-queue.md), whose decision raised the admission
  wait above `ATTEMPTS_PER_ADMISSION` whole run deadlines and could size that window only from
  reading the code.
- 2026-09-11: read against the tree and the trigger has not fired. `_placed` in
  `cortex_core/runner.py` still writes one warning per re-run, with `task_id`, `model` and the
  first attempt's `detail`, and `reran_on_cpu` in `subagent_outcome.py` still folds that detail
  into the one result's `detail` string; `SubagentResult` still has `task_id`, `output`, `ok`,
  `detail` and `tainted` and no field naming a placement or an attempt count, and the tool audit
  still records `result_chars` for the batch and nothing per attempt. No runbook shows the re-run
  line, so it is under no sample check either. `DEFAULT_ADMISSION_WAIT_S` is 7200.0 since
  2026-08-25 and `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` is 2400.0, and neither has moved. The first half
  of the trigger became observable on 2026-09-08, when the runner gained a warning at the refusal
  itself, `a spawn was refused before it ran`; no deployment has been recorded refused on it.
- 2026-09-17: read again and still open; neither half has fired. The three numbers the hold is
  sized from have not moved since the entry above (`git log -S` on each finds no commit after
  2026-08-25), `_placed` still writes the one warning with `task_id`, `model` and `detail`, and
  `SubagentResult` still has no field naming a placement or an attempt. The file audit sink added
  on 2026-09-17 keeps the tool trail across a restart, but it writes one line per tool call, so a
  spawn re-run on the CPU is still invisible there. What moved is the retune half: the same day the
  subagents override began passing `CORTEX_SUBAGENTS_ADMISSION_WAIT_S` and
  `CORTEX_SUBAGENTS_RUN_TIMEOUT_S` into the brain by bare name, so a deployment can now retune
  either from its shell or `.env` without a change in the tree, and the trigger now names the grep
  that counts a value written into a compose file. Two corrections to the entry above: the refusal
  warning is sampled in `docs/runbooks/subagents-cpu.md` (line 355), and the re-run warning is
  named in that runbook's prose at line 503 but printed as no sample line, which is why no sample
  check covers it.
- 2026-09-24: not fired. The three numbers have not moved, no compose file gives either variable a
  value, and `SubagentResult` still has `task_id`, `output`, `ok`, `detail` and `tainted`. The only
  runner change since added an `admitted` callback for the turn heartbeat. Two corrections to the
  entry above: the refusal warning is sampled at line 216 of `docs/runbooks/subagents-cpu.md`, and
  that runbook no longer names the re-run warning at all; line 149 says only that a stalled attempt
  is re-run once on the CPU.
