# A bounded admission wait

**Status:** landed 2026-08-09
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

The entry read: "*Fix when it bites.* Admission waits with no timeout and no
queue-depth bound. Depth-1 guarantees the queue drains while admitted runs terminate, and
`MAX_SPAWN_BATCH` bounds one call, so nothing is unbounded in practice today. The trigger is a
real deployment showing a turn stalled in admission long enough to matter; the fix is a timeout
design over a `Clock`, refusing with the same typed error, not a policy flip."
`ResourceBudgetScheduler.admit` now refuses after `wait_timeout_s` seconds with the same typed
`SubagentAdmissionError` the runner already degrades to an `ok=False` result, wired from
`CORTEX_SUBAGENTS_ADMISSION_WAIT_S` (default 3600 s, zero meaning never queue). Four things
about it, two of them corrections to this entry's own text.
**"Nothing is unbounded in practice today" was the false half**, and the read-timeout entry
below said why without either of them noticing: a wedged `llama-server` stream held its
admission forever, so the queue behind it never moved, and depth-1 plus `MAX_SPAWN_BATCH` bound
how *many* wait rather than how *long*. That sibling landed hours earlier the same day, which is
what let this one close ahead of its trigger: with a stall now bounded on both generation
clients, the remaining ways for a queue to stop moving are a runaway generation (the entry at
the bottom of this file) and nothing else anybody has named, so leaving the wait itself
unbounded had stopped being defensible.
**The port really was unchanged, and this time it was checked rather than claimed.** This area's
header asserts that blanket over all three ports and the index's standing warning names the pair
where it broke, so the signature was opened first:
`admit(request) -> AbstractAsyncContextManager[None]` carries nowhere to put a per-spawn bound
and needs none, because the bound is policy the budget owns, exactly like the two numbers already
on that constructor. What the port gained is a sentence of contract, that an implementation which
queues owes a bound on that queue and the same typed refusal when it elapses; `AdmitAllScheduler`
satisfies it vacuously, having no queue, so the drain contract suite needed no new case and the
twin is untouched.
**"A timeout design over a `Clock`" is the other correction.** The bound is `asyncio.timeout`
around the wait loop, the mechanism `drain` already uses on this very condition object, for three
reasons the addendum argues: a duration belongs on the loop's monotonic clock rather than on the
wall clock `Clock.now()` reads, the `Clock`/`Sleeper` pair exists for poll loops that would
otherwise force real-time tests (this is a bounded wait on an event, whose timeout path an
already-expired bound drives in microseconds), and one class should not bound its two waits two
different ways. A `Clock` here would have been a decoration.
**The number is derived rather than guessed**, which matters because a bound that refuses a legitimately
queued spawn is worse than the unbounded wait it replaces: `MAX_SPAWN_BATCH` is 8, the shipped
budget admits two at a time, and one entry holds a backend, and so a model lease, per placement
target (4.8 s through two backend objects against 10.0 s through one), so the admitted pair
overlaps while one spawn is GPU-placed and the other overflows and serializes only while both
land on the same target. A whole CPU subtask measures 200 to 300 s, so the last of a full batch
is admitted about **900 s** in while the pair overlaps and about **1800 s** in while it
serializes, and the bound is twice the serial figure, which makes it an upper bound over both
rather than an equality on either.
**That premise was corrected on the day the bound landed.** The derivation first read the backend
lock as unconditional, which the roster measurement recorded the day before had already ruled out
for an entry that omits `gpu_endpoint`: two lock objects front one server, so its spawns overlap
two ways. The number did not move, a closed GPU tier still leaving the serial case, but the claim
did, from an equality to a bound four times the wait the shipped stack produces. Said plainly
rather than left to be found: two full batches queued at once lose their tail to the bound while
the entry serializes and clear it while the pair overlaps, and the first is the deployment that
should raise the knob. **The queue-depth half did not ship** and is the entry below.
**The correction needed a second pass the same day, because the first one under-reported its own
reach.** It named the comment, the test, two documents and this entry, and four further sites
went on restating the equality in the present tense: the operator guidance in
[runbooks/subagents-cpu.md](../../runbooks/subagents-cpu.md), the same knob's comment in
`docker/docker-compose.subagents.yml`, the contract sentence in
[modules/brain-orchestrator.md](../../modules/brain-orchestrator.md) that its twin in
`brain-core.md` had already been fixed against, and the row for this area in the
[index](../index.md). The runbook was the one that mattered, being where an operator sizes the
knob: it asserted 1800 s for the shipped budgets, cited the corrected addendum for the premise
that addendum now denies, and told a reader that queuing two batches at once needs the bound
raised, which is false wherever the pair overlaps (2100 s clears 3600 s) and true only where a
closed GPU tier or an ask that never fits leaves both spawns on one target (4200 s). Both boxes
in that runbook now scope the serialization to a shared target and name the overlap as capped at
two rather than absent, and the advice names the placement it applies to. The lesson is the
cheap one: a correction's scope claim is itself a claim, and grepping the mechanism ("serialize",
"one backend") alongside the numbers is what finds the copies that paraphrase instead of quote.

## Trail

- 2026-07-16: Opened by the hard budget wall's close, as one of the two waits nothing bounded.
- 2026-08-09: Landed ahead of its trigger and with half of it declined, recorded at the
  [ADR-0012 bounded-admission-wait addendum](../../adr/ADR-0012-resource-governance.md). `admit` now
  refuses after `CORTEX_SUBAGENTS_ADMISSION_WAIT_S` (3600 s by default, zero meaning never queue)
  with the same typed error the runner already degrades to an `ok=False` result. Its sibling read
  timeout landing hours earlier is what removed the excuse for leaving the wait unbounded, and the
  queue-depth half it declined took its place.
- 2026-08-09: The derivation's premise was corrected the same day, from an equality to an upper
  bound four times the wait the shipped stack produces, and the correction needed a second pass
  because the first under-reported its own reach: four further sites still restated the equality in
  the present tense, the operator guidance in the subagents runbook being the one that mattered.
- 2026-08-09: The same premise was folded into this derivation and deliberately not into the spawn
  tool's advertised trade-off in the subagents area, which describes the same backend lock and stayed
  conservative, on the reason that a derivation pinned by a test is corrected rather than left
  conservative.
- 2026-08-11: The 200 to 300 s whole-subtask figure this derivation multiplies out into 900 s and
  1800 s was measured as an underestimate by a factor of two for a summarization, which is now an
  entry of its own.
