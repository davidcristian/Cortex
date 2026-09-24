# A queue-depth bound

**Status:** open, waiting for its trigger
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)
**Trigger:** The first deployment seen reaching the wait bound, which appears as the runner's
`a spawn was refused before it ran` warning (logger `cortex_core.runner`) whose `reason` field
contains `outlasts the deployment's admission bound`. The brain writes that line to its container's
own output and to no file, so it is read with `docker compose logs brain` and lasts only as long as
the container does. The same text is also in the stored `SubagentResult` under
`cortex:task:{id}:result` in Redis, whose TTL of 3600 s is half the shipped bound.
**Verified:** 2026-09-24

The wait bound refuses late, after the caller has already paid
`CORTEX_SUBAGENTS_ADMISSION_WAIT_S`, which ships at 7200 s. A depth bound would refuse early, once
the queue is already longer than the budget can drain. Only the wait bound can be derived today,
because the scheduler tracks charges and no durations: it knows a waiter asks for 2.0 cpus and has
no idea whether that is thirty seconds of work or five minutes, so any depth number is a guess where
the wait number is arithmetic over measurements. What stays open is a spawn joining an already
hopeless queue and paying the whole bound before it is told.

The one duration the deployment does bound is the wrong end of the range. Since 2026-08-25 a task
holds its admission for at most `ATTEMPTS_PER_ADMISSION` run deadlines, 4800 s at the shipped
numbers, and `SubagentsConfig._the_run_deadline_must_fit_inside_the_queue_for_it` refuses at boot
any wiring where that hold reaches the wait. A depth rule cannot follow from it, because that is an
upper bound and a depth rule needs a lower one. Turning 4800 s into a depth asks when a waiter is
guaranteed admission inside 7200 s, and with two admitted at a time the answer is one waiter ahead
of it and no more. A rule refusing at a depth of two would have refused six of the eight spawns in
the batch that was actually measured, whose last member was admitted 1624.6 s in.

The fix is a waiter count in `ResourceBudgetScheduler` and the same typed refusal. The port's
signatures take it without changing: `PlacementRequest` has `model`, `vram_gb`, `cpus` and
`memory_gb` and no duration, and a depth number is the budget's policy rather than a per-spawn
request, so it belongs on the constructor beside the two budgets and the wait. What the port does
owe is the sentence the wait bound owed it: its contract says that callers over budget wait, and a
depth refusal is a caller that does not.

## History

- 2026-08-09: Opened by the bounded admission wait's close, which shipped one of the two refusals
  that entry asked for and declined this one.
- 2026-09-08: Checked and not fired, and three sentences repaired. The bound is 7200 s rather than
  the hour this entry was written against. Driving `ResourceBudgetScheduler(4.0, 8.0)` with eight
  concurrent requests of `cpus=2.0, memory_gb=3.0` admits two and leaves six waiting, and the six
  exist only on the `asyncio.Condition`'s own waiter deque, since nothing in the class names them.
  The trigger gained the two places a refusal can be seen, neither of them a log line at the time,
  which opened [R-614](614-a-refused-spawn-reaches-no-log-line.md).
- 2026-09-11: Not fired, and the reading the trigger asks for was taken. Redis was started alone
  from its stored append-only volume and scanned: 75 keys, all session keys, and `cortex:task:*`
  matched none. `DEFAULT_ADMISSION_WAIT_S` is 7200.0 in `scheduler.py`, `_TASK_TTL_SECONDS` is 3600
  in `cortex_session/tasks.py`, `ATTEMPTS_PER_ADMISSION` is 2 and `MAX_SPAWN_BATCH` is 8, and the
  boot validator is in `config_subagents.py`.
- 2026-09-17: Not fired, and the trigger restated, since R-614 closed on 2026-09-08: the warning is
  now written in the `except SubagentAdmissionError` of `cortex_core/runner.py` with `task_id`,
  `model` and `reason`. Both places were looked at. `docker ps -a` lists no brain container, and
  Redis held 75 keys with `cortex:task:*` matching none. Every number above was read again and
  holds, and the three port signatures in `ports.py` are unchanged.
- 2026-09-24: Not fired, read from the tree only: Docker was left to a detached GPU run, so neither
  the brain's output nor Redis was looked at, and the 2026-09-17 line is the latest reading of
  both. The warning, the refusal text in `scheduler.py`, the four constants, the boot validator
  and the four `PlacementRequest` fields (`placement.py`) are unchanged.
