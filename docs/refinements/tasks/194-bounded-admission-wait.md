# A bounded admission wait

**Status:** done 2026-08-09
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

Admission waits had no timeout. `ResourceBudgetScheduler.admit` now refuses after `wait_timeout_s`
seconds with the same typed `SubagentAdmissionError` the runner already turns into an `ok=False`
result, wired from `CORTEX_SUBAGENTS_ADMISSION_WAIT_S` (default 3600 s, zero meaning never queue).

The entry's claim that nothing was unbounded in practice was false, and the read-timeout entry below
said why: a wedged `llama-server` stream held its admission forever, so the queue behind it never
moved, and depth-1 plus `MAX_SPAWN_BATCH` bound how many wait rather than how long. That sibling
closed hours earlier the same day, which is what let this one close ahead of its trigger.

The port really was unchanged, and it was checked rather than assumed:
`admit(request) -> AbstractAsyncContextManager[None]` has nowhere to put a per-spawn bound and needs
none, because the bound is policy the budget owns. What the port gained is a sentence of contract,
that an implementation which queues owes a bound on that queue and the same typed refusal when it
elapses. `AdmitAllScheduler` satisfies that with no queue, so the contract suite needed no new case.

The bound is `asyncio.timeout` around the wait loop rather than the `Clock` design the entry
proposed. A duration belongs on the loop's monotonic clock rather than the wall clock `Clock.now()`
reads; the `Clock`/`Sleeper` pair exists for poll loops that would otherwise force real-time tests,
and this is a bounded wait on an event; and one class should not bound its two waits two different
ways, since `drain` already uses `asyncio.timeout` on this same condition object.

The number is derived rather than guessed, because a bound that refuses a legitimately queued spawn
is worse than the unbounded wait it replaces. `MAX_SPAWN_BATCH` is 8, the shipped budget admits two
at a time, and one roster entry holds a backend, and so a model lease, per placement target (4.8 s
through two backend objects against 10.0 s through one). So the admitted pair overlaps while one
spawn is GPU-placed and the other overflows, and runs one after the other only while both go to the
same target. A whole CPU subtask measures 200 to 300 s, so the last of a full batch is admitted
about 900 s in while the pair overlaps and about 1800 s in while it does not, and the bound is twice
the second figure, which makes it an upper bound over both rather than an equality on either.

Two full batches queued at once lose their tail to the bound where the entry runs one after the
other, and clear it where the pair overlaps, and the first is the deployment that should raise the
setting. The queue-depth half did not ship and is the entry below.

## History

- 2026-07-16: Opened by the hard budget limit's close, as one of the two waits nothing bounded.
- 2026-08-09: Closed ahead of its trigger and with half of it declined, recorded at
  [ADR-0012 decision 11](../../adr/ADR-0012-resource-governance.md).
- 2026-08-09: The derivation's premise was corrected the same day, from an equality to an upper
  bound four times the wait the shipped stack produces, because the backend lock is not
  unconditional: an entry that omits `gpu_endpoint` has two lock objects fronting one server. The
  correction needed a second pass, because the first under-reported its own reach: four further
  places still stated the equality in the present tense, the operator guidance in
  [runbooks/subagents-cpu.md](../../runbooks/subagents-cpu.md) being the one that mattered, since it
  is where an operator sizes the setting. The lesson is that a correction's scope claim is itself a
  claim, and grepping the mechanism alongside the numbers is what finds the copies that paraphrase
  instead of quote.
- 2026-08-09: The same premise was deliberately not folded into the spawn tool's advertised
  trade-off, which stays conservative.
- 2026-08-11: The 200 to 300 s whole-subtask figure this derivation multiplies out was measured as
  an underestimate by a factor of two for a summarization, which is now an entry of its own.
