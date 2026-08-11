# A queue-depth bound

**Status:** open, fix when it bites
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)
**Trigger:** The first deployment observed hitting the wait bound.

A queue-depth bound, to refuse a hopeless queue early rather than an hour late.
Opened 2026-08-09 by the close above, which shipped one of the two refusals that entry
asked for. They answer different questions: the wait bound refuses **late**, after the caller has
already paid the hour, while a depth bound refuses **early**, when the queue is already provably
longer than the budget can drain. Only the wait bound is derivable today, because the scheduler
holds charges and no durations: it knows a waiter asks for 2.0 cpus and has no idea whether that
is thirty seconds of work or five minutes, so five waiters asking 0.5 each and five asking 2.0
look identical to it and any depth number is a guess where the wait number is arithmetic over
measurements. What that leaves open is a spawn joining an already hopeless queue and paying the
whole bound before it is told, with `MAX_SPAWN_BATCH` and depth-1 still the only things bounding
how long the queue can get. The trigger is the first deployment observed hitting the wait bound,
which is also the first one with a measured drain rate to derive a depth from; the fix is a
waiter count in `ResourceBudgetScheduler` and the same typed refusal, behind the same unchanged
port for the same reason the wait bound was (the number is the budget's policy, not a per-spawn
ask), which is a claim the close above establishes by having opened the signature rather than
one this entry is asserting fresh.

## Trail

- 2026-08-09: Opened by the bounded admission wait's close, which shipped one of the two refusals
  that entry asked for and declined this one, because the scheduler holds charges and no durations,
  so any depth number is a guess where the wait number is arithmetic over measurements.
