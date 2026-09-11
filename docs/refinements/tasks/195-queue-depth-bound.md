# A queue-depth bound

**Status:** open, fix when it bites
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)
**Trigger:** The first deployment observed hitting the wait bound. Reading it is harder than the
sentence suggests, because nothing logs the refusal: it reaches the cortex as the spawn tool's
aggregate text and reaches the store as a `SubagentResult` whose `detail` carries
`outlasts the deployment's admission bound`, under `cortex:task:{id}:result` in Redis at a TTL of
3600 s, which is half the shipped bound. So the reading is a scan of those keys for that phrase,
taken within an hour of the refusal, and R-614 is the entry for making it a log line instead.
**Verified:** 2026-09-11

A queue-depth bound, to refuse a hopeless queue early rather than a whole bound late.
Opened 2026-08-09 by the close above, which shipped one of the two refusals that entry
asked for. They answer different questions: the wait bound refuses **late**, after the caller has
already paid `CORTEX_SUBAGENTS_ADMISSION_WAIT_S`, which ships at 7200 s, while a depth bound
refuses **early**, when the queue is already provably longer than the budget can drain. Only the
wait bound is derivable today, because the scheduler holds charges and no durations: it knows a
waiter asks for 2.0 cpus and has no idea whether that is thirty seconds of work or five minutes, so
five waiters asking 0.5 each and five asking 2.0 look identical to it and any depth number is a
guess where the wait number is arithmetic over measurements. What that leaves open is a spawn
joining an already hopeless queue and paying the whole bound before it is told, with
`MAX_SPAWN_BATCH` and depth-1 still the only things bounding how long the queue can get.

**The one duration the deployment does bound is the wrong end of the range.** Since 2026-08-25 a
task holds its admission for at most `ATTEMPTS_PER_ADMISSION` run deadlines, 4800 s at the shipped
numbers, and `SubagentsConfig._the_run_deadline_must_fit_inside_the_queue_for_it` refuses at boot
any wiring where that hold reaches the wait. A reader arriving at this entry from that validator
may expect the depth to follow from it, and it does not, because that is an upper bound and a depth
rule needs a lower one. Turning 4800 s into a depth asks when a waiter is *guaranteed* admission
inside 7200 s, and with two admitted at a time the answer is one waiter ahead of it and no more.
A rule refusing at a depth of two would have refused six of the eight spawns in the batch that was
actually measured, whose last member was admitted 1624.6 s in. Nothing bounds a run from below, so
nothing can prove a queue hopeless; the guess this entry defers is a guess for the same reason it
always was, one level further down.

The fix is a waiter count in `ResourceBudgetScheduler` and the same typed refusal. The port's
signature carries it without changing: `admit(request)`, `drain(*, timeout_s)` and `undrain()` were
opened and read again on 2026-09-08, `PlacementRequest` still carries `model`, `vram_gb`, `cpus` and
`memory_gb` and no duration, and a depth number is the budget's policy rather than a per-spawn ask,
so it belongs on the constructor beside the two budgets and the wait exactly as the wait did. What
the port does owe is the sentence the wait bound owed it: its contract says that over budget
callers wait, and a depth refusal is a caller that does not.

## Trail

- 2026-09-08: trigger swept and not fired, and three of this entry's sentences repaired. The bound
  is 7200 s rather than the hour this entry was written against. What a full batch leaves behind was
  measured today rather than reasoned: driving `ResourceBudgetScheduler(4.0, 8.0)` with eight
  concurrent asks of `cpus=2.0, memory_gb=3.0` admits **two** and leaves **six** waiting, and the
  scheduler's whole state at that moment is `_cpu_budget`, `_mem_budget_gb`, `_wait_timeout_s`,
  `_cpu_used`, `_mem_used_gb`, `_in_flight` and `_draining`, so the six exist only on the
  `asyncio.Condition`'s own waiter deque and nothing in the class names them. The port was opened
  rather than quoted, and it does carry the change without a signature edit, though its contract
  sentence does not. The hold relation added on 2026-08-25 was read as a possible source for the
  depth number and rejected with the arithmetic above. The trigger gained the two places a refusal
  can be seen, neither of them a log line, which opened
  [R-614](614-a-refused-spawn-reaches-no-log-line.md).
- 2026-08-09: Opened by the bounded admission wait's close, which shipped one of the two refusals
  that entry asked for and declined this one, because the scheduler holds charges and no durations,
  so any depth number is a guess where the wait number is arithmetic over measurements.
- 2026-09-11: **Not fired**, and the reading the trigger prescribes was taken rather than skipped.
  The stack was down when this slot started, so redis was started alone from its persisted
  append-only volume and scanned: it held 75 keys, every one of them a session key, and
  `cortex:task:*` matched none, so no `SubagentResult` carrying
  `outlasts the deployment's admission bound` exists to find, and no brain has been running that
  could have refused one. Redis was stopped again afterwards. The numbers above were reread from
  the tree: `DEFAULT_ADMISSION_WAIT_S` is 7200.0 in `scheduler.py`, where the phrase is
  `ADMISSION_WAIT_MSG`; `_TASK_TTL_SECONDS` is 3600 in `cortex_session/tasks.py`, which also
  spells the `cortex:task:{id}:result` key; `ATTEMPTS_PER_ADMISSION` is 2 and `MAX_SPAWN_BATCH`
  is 8; the boot validator is in `config_subagents.py`. `ResourceBudgetScheduler` still holds the
  seven fields listed above plus the `asyncio.Condition` they wait on, `PlacementRequest` still
  carries `model`, `vram_gb`, `cpus` and `memory_gb`, and the port's three signatures in
  `ports.py` are unchanged.
