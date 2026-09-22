# ADR-0024: Transport retry, deadlines and turn gaps

**Status:** Accepted (2026-09-22)

## Context

The body's `BrainSeamClient` (the tonic adapter behind the `body_core::BrainTransport` port) is a
thin translation with no retries. The brain is a supervised local process: it restarts after a
model swap, or drops a loopback connection for a moment, and is back within seconds. A read from
the overlay therefore failed outright where a retry a moment later would have succeeded. A brain
can also accept a connection and then send nothing. The overlay's `useLink` keeps an `inFlight`
flag that is cleared in the promise's `finally`, so one probe that never resolves disables every
later probe, and a turn whose stream stops leaves the thinking indicator visible for as long as
the process runs.

Three rules from AGENTS.md shape the design. The adapter stays thin, so retry policy cannot live
in `BrainSeamClient`. The core is pure, so a backoff sleep or a deadline is an injected effect.
The whole loop is covered 100% without a network or a wall clock.

## Decision

### The decorator and what it retries

1. **Retry is a decorator over the port.** `RetryingTransport<T: BrainTransport, S: Sleeper>`
   (`body_core::retry`) is itself a `BrainTransport` wrapping an inner transport, so it is tested
   in full against a fake. `BrainSeamClient` stays thin and the recovery logic sits on top of it.

2. **Only a repeatable call is retried, and `converse` never is.** A turn may run tools, stream
   partial output and store messages before it fails, and its `decisions` stream can be consumed
   once. The overlay treats a failed turn as final and the user resends.

3. **Transient means `Connection` or `Rpc{Unavailable}`; everything else is final.**
   `is_transient` retries an unreachable brain and `Unavailable` (which the brain returns for a
   store failure). `Protocol`, `Timeout` and every other status are final. The brain's gRPC server
   returns only `UNAVAILABLE`, `UNAUTHENTICATED` and the generated default's `UNIMPLEMENTED`.
   `RESOURCE_EXHAUSTED` is returned between these two services only by the body's `BodyService`,
   about a capture too large to send, which a repeat would send again; `ABORTED` is a convention no
   handler uses; `DEADLINE_EXCEEDED` is decision 13's. The test
   `the_codes_a_wider_table_would_have_added_are_still_terminal` asserts all three stay final.

4. **Bounded exponential backoff with equal jitter.** `RetryPolicy` (pure, `Copy`) holds
   `max_attempts` (including the first), `base_delay`, `multiplier` and `max_delay`; the delay
   before retry *k* is `min(base_delay · multiplierᵏ, max_delay)`, computed with a saturating
   multiply. Each delay is scaled by `0.5 + 0.5 * unit()` from a `Randomness` port, so half the
   delay is a minimum: the wait gives a restarting brain time, and a zero draw would spend an
   attempt immediately. A draw out of range is clamped and a non-finite one counts as the full
   delay. `FullDelay`, the constant-1 source, is what `RetryingTransport::new` uses;
   `with_randomness` opts in, and the shell's `ShellRandomness` draws from std's `RandomState`.

5. **Time is an injected effect.** `Sleeper::sleep(Duration)` is the wait between attempts and
   `Sleeper::bounded(deadline, call) -> Option<T>` is the bound on one attempt, where `None` means
   the deadline expired and the call was dropped. For the gRPC adapter that resets the stream, so
   the brain stops working on it. `TokioSleeper` lives in the shell; the fakes record waits and
   either grant or expire a call outright.

6. **A lazy channel lets the decorator cover the dial.** `connect_lazy_with_token` builds the
   client over `Channel::connect_lazy`: construction fails only on a bad URI or token, and each RPC
   re-establishes the connection, so a briefly-down brain fails with `Connection` and is retried.
   The eager `connect` and `connect_with_token` still fail immediately.

7. **The shell composes it per command, from one plan read once.** `seam::connect` builds
   `RetryingTransport::with_randomness` over `connect_lazy_with_token`, `TokioSleeper`,
   `ShellRandomness` and `plan_from_env()` for the session, reminder and preference calls.
   `converse.rs` runs the lazy constructor first as a configuration check, so a bad URI or token
   fails immediately rather than being retried as a `Connection`; it wraps its eager dial in
   `retry_with` and `within_deadline`, which is safe because the turn has not begun until the dial
   succeeds; and it hands the client to a `RetryingTransport` for decision 21. The settings are all
   `CORTEX_BRAIN_` variables: `RETRY_ATTEMPTS` 3, `RETRY_BASE_MS` 200, `RETRY_MULTIPLIER` 2,
   `RETRY_MAX_MS` 2000, `RETRY_JITTER` on (`off` removes the jitter), `PROBE_BUDGET_MS` 1000,
   `PROBE_DEADLINE_MS` 250, `CALL_DEADLINE_MS` 5000, `TURN_FIRST_GAP_MS` 600000,
   `TURN_IDLE_GAP_MS` 14400000 and `TURN_HEARTBEAT_GAP_MS` 120000 (ADR-0069).

### Repeatability and the plan

8. **Repeatability is a property of the method, decided for every method.** `SeamMethod` names
   every port call and `repeatable()` classifies each in one `match`, so a new variant does not
   compile until someone decides. A repeat must neither duplicate an effect nor change the result,
   which are two separate tests: `AckReminder` is idempotent on the brain side, but an ack whose
   reply was lost has already cleared the reminder, so its retry would return `false` about a
   reminder this very call dismissed. The five reads (`Health`, `ListSessions`,
   `GetSessionMessages`, `ListDueReminders`, `GetPreferences`) repeat. `Converse`, `AckReminder`
   and the catalog writes (`RenameSession`, `DeleteSession`, `SetSessionHoisted`, `SetPreference`)
   get one attempt, since a lost reply must not reapply a value the user's next action reversed.

9. **`RetryPlan::policy_for` is the single decision point.** It returns a schedule for a repeatable
   method and `None` otherwise, and the decorator runs a `None` through the same loop on
   `RetryPolicy::ONCE` rather than branching past it, because a bypass left the loop reachable only
   by a refused call and so uncovered. Repeatability is checked before transience: a status never
   proves the brain did not already run the call, so `is_transient` is necessary, never sufficient.

10. **The `Health` probe's schedule is trimmed to a budget.** The connection indicator shows the
    probe's result ([ADR-0011](ADR-0011-body-v1.md)), so time spent retrying is time the dot shows
    a state the connection has stopped proving. The probe runs
    `reads.within(probe_budget, probe_deadline)`: the same delays, with attempts dropped until
    `attempts × deadline + backoff` fits, one always kept, so the early waits stay long enough for
    a restarting brain. **`Down` arrives within `max(probe_budget, probe_deadline)`**, raising the
    read settings never slows the probe, and at the defaults the probe keeps two attempts
    (250 + 200 + 250 ms fits 1 s, a third does not).

### Deadlines

11. **Every unary attempt is bounded, in the core.** `retry::deadline::within_deadline` wraps each
    attempt in `Sleeper::bounded`, and is public so the shell can bound its `converse` dial too.
    `RetryPlan::deadline_for` returns 250 ms for `Health`, which is synchronous and lock free on
    the brain side and replies in single-digit milliseconds, and 5 s for the other unary calls,
    which are store operations over loopback, short enough that the switcher reports failure while
    the user watches. The writes are bounded though never retried. `Converse` gets no deadline,
    since a turn is long by design, written as `Duration::MAX` rather than a branch in generic code.

12. **An expiry is its own failure.** `TransportError::Timeout { after }` is a fourth variant for a
    fourth fact: `Connection` means nothing accepted the call, `Rpc` means the brain replied, and a
    timeout means the body stopped waiting. `LinkStatus::from_error` maps it to `Down`, since
    `Degraded` means the brain replied, and the detail (`no reply within 250ms`) separates a stuck
    brain from an absent one.

13. **A timeout is final.** Retrying an expired deadline adds load exactly when the brain is too
    slow to reply; a timeout is the body's decision to stop waiting and says nothing about the next
    attempt, so a call that needs longer needs a longer deadline; and the abandoned attempt may
    still be running on the brain side, so a retry would stack a duplicate on it.

14. **The deadline is never tonic's.** tonic's own expiry arrives as `Status::cancelled("Timeout
    expired")` with the originating `tonic::transport::Error` on its source chain, which the
    adapter classifies as `Connection`, so a deadline enforced by tonic would be retried silently.
    `tonics_own_expired_timeout_classifies_as_a_retryable_connection_failure`
    (`body/crates/rpc/tests/client.rs`) drives a real expiry and fails if that changes.
    `Request::set_timeout` only writes the `grpc-timeout` header, and the channel's `GrpcTimeout`
    layer starts a local timer from it, so announcing a deadline and starting a tonic timer are the
    same action ([deadline measurements](../readings/rpc-deadlines.md)).

15. **The deadline is announced a grace margin longer than it is enforced.**
    `RetryPlan::announced_deadline_for` is the enforced deadline plus `ANNOUNCED_DEADLINE_GRACE_MS`
    (250), and `None` for `Converse`. The core's timer starts before the call is polled and tonic's
    layer sees the request after, so the longer announcement cannot expire first while the runtime
    schedules. The margin is sized by the stall that ordering must survive (a runtime stalled past
    both deadlines polls the call first): it is about twenty-three times the widest overlap
    measured under twice-oversubscribed load
    ([abandoned-call measurements](../readings/abandoned-call-remaining.md)). The loopback round
    trip and header parse cost about a millisecond, and tonic's truncating encoder loses nothing on
    the two shipped announcements, which reach a grpc-python brain as exactly 500 ms and 5250 ms.
    The brain works at most the margin past the moment the body stopped waiting. `SeamCall`
    (`body/crates/rpc/src/call.rs`) holds the channel, the token (redacted in a hand-written
    `Debug`) and the plan, and builds the generated client per call so the interceptor sets each
    call's header. A `DEADLINE_EXCEEDED` from the brain maps to `Timeout { after }` when the call
    announced a deadline, and stays `Rpc{DeadlineExceeded}` when it announced nothing.

16. **Past the millisecond step, nothing is announced.** tonic truncates `grpc-timeout` onto the
    most precise unit whose count fits eight digits, so past 99,999,999 ms (about 27.8 hours) the
    unit is a whole second and the announcement would start tonic's timer under the enforced bound
    for 749 of every 1000 millisecond remainders. `MAX_ANNOUNCED_DEADLINE_MS` in `call.rs` is that
    limit, and an announcement past it, including one tonic's encoder would panic on, is dropped
    rather than clamped: the brain loses a hint, and the core's bound still ends the call. The
    setting parses with no ceiling, so that range is one variable away, and `scripts/crosscheck.py`
    compares the constant with the figure in [body-rpc.md](../modules/body-rpc.md).

17. **What the brain does with the announcement is decided separately.** `grpc.aio` cancels the
    handler when the body resets the stream, and the header adds a bound on the brain's own clock
    for a killed body or a half-open connection. The brain logs an abandoned call and changes no
    behaviour ([ADR-0061](ADR-0061-abandoned-call-line.md)).

### A turn's silence

18. **A turn is bounded by its silence, never by its length.** `retry::gap::within_gaps` bounds the
    gap between the stream's events; every delta, tool activity, tool outcome, status and confirm
    event restarts the clock, so a turn may run for hours while events keep arriving. A heartbeat
    counts as one period of it instead ([ADR-0069](ADR-0069-turn-heartbeat.md)). It composes
    `Sleeper::bounded` over one poll of the stream. `RetryPlan::gaps_for` is `Some` for `Converse`
    alone, and `retry_plan.rs` asserts over every variant that **each call is bounded by a clock on
    the call or on its silence, never both**. A turn still announces nothing on the wire.

19. **The first-event gap is ten minutes.** `DEFAULT_TURN_FIRST_GAP_MS` (600000) is the sum of the
    brain's own bounds before a first event, each ending in a reported failure (the swap's pool
    drain, 60 s, its model load, 300 s, and the first-token stall ceiling, 120 s), plus margin for
    recall, prefill and a first round that streams nothing visible. It is about four times the
    slowest first event measured on this machine's GPU, which was loading the deep tier plus its
    first token ([ADR-0005](ADR-0005-llamacpp-engine.md), decision 7).

20. **The idle gap is four hours.** The longest legitimate silence is a delegated subtask that
    calls no tool: it may wait `DEFAULT_ADMISSION_WAIT_S` (7200 s) for admission, then hold that
    admission for `ATTEMPTS_PER_ADMISSION` runs of `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` (2 × 2400 s),
    12000 s in all ([ADR-0047](ADR-0047-delegated-run-bound-ordering.md)), and
    `DEFAULT_TURN_IDLE_GAP_MS` (14400000) is a fifth above that. A batch adds nothing, since
    `spawn_subagents` requests every admission at once under one `asyncio.gather`. The gap's doc
    comment quotes both brain constants and `scripts/boundscouplings.py` compares those quotes with
    the declarations. The gap is not widened only for turns that announce a delegation, because
    progress is sent through a sink that drops events when its buffer is full. A dead brain is
    reported within minutes by the heartbeat gap instead, so this bound only ends a turn that makes
    no progress; a deployment without delegation can set it to the first-event figure.

21. **An expired gap is reported.** The stream yields one `Err(TransportError::Timeout { after })`
    and ends, dropping the inner stream, which resets the turn. Ending silently would leave the
    reply streaming, since the overlay finishes one only on a final event or an error. `linkFailed`
    maps a `timeout` to `down`, so the reply keeps the words that arrived and the dot goes red,
    while the user's own Stop records no error. `RetryingTransport::converse` applies the gaps, and
    the shell's turn path runs through it.

### Declined and deferred

22. **No retry budget and no circuit breaker.** Only the five reads reach the loop, an expiry is
    final, and nothing on the body polls, so a flapping brain costs at most two extra connect
    attempts per user action against a loopback peer that refuses immediately. A circuit breaker
    would need state outliving the per-command transport and a port that reads the clock, and a
    call refused by stale open state reports a connection state nobody asked the brain about. A
    body-side poller, a remote `CORTEX_BRAIN_ADDR`, or a blind retry costing seconds reopens this.

23. **Reconnecting a turn before its first event is deferred.** The brain stores the user message
    before inference and a tool may run before any event is sent, so "no event seen" never means
    "no work done", and `UserTurn` has no request identity, so a resend runs the turn twice. A safe
    version needs a client request id, a deduplication and event registry in the hot store, and a
    rejoin path ([R-023](../refinements/tasks/023-converse-reconnect-first-event.md)). It becomes
    necessary once mid-turn evictions are routine; no composed stack swaps while
    `CORTEX_ESCALATION` is off.

24. **Live tests count attempts rather than elapsed time.** Where a host's network stack drops a
    dial to a closed port instead of refusing it, a probe against a dead address returns at its
    first deadline, so a wall-clock lower bound cannot tell one expired attempt from two refused
    ones ([deadline measurements](../readings/rpc-deadlines.md)). `dial_dropping_peer`
    (`body/crates/rpc/tests/live.rs`) drops and counts every dial, and
    `the_probe_trims_its_attempts_where_a_read_spends_them_all` asserts two probe attempts where a
    read uses all it may. The dead-address test asserts only `Down` inside the budget.

## Consequences

- A down brain costs a read up to `max_attempts - 1` backoff waits plus each attempt's deadline
  before the error is reported. A brain returning `Unavailable` for a lasting condition is retried.
- No call on this interface is unbounded; a read slower than 5 s now fails with a typed error. A
  turn silent past its gap ends and settles the indicator.
- The check is only as strong as the enum: a new port method forces a `SeamMethod`, a wrong
  existing variant is a misstatement rather than an accident, and `EVERY_METHOD` lists all eleven.
- `RetryingTransport::new` and `with_randomness` take `impl Into<RetryPlan>`. `body_core` depends
  on `async-stream`, a generator macro over `futures-core`, and uses no runtime and no I/O.

## Alternatives rejected

- **Retry inside the adapter.** Policy is business logic, and an adapter holds none.
- **A tonic timeout as the deadline.** Its expiry is a retryable `Connection` (decision 14).
- **Clamping or rounding the announcement onto tonic's steps, or capping the setting.** A clamp
  runs the race deliberately; rounding reimplements a private encoder that can change under a
  version bump; a cap leaves `RetryPlan`'s public fields open and changes a bound the operator set.
- **A configurable retryable-code table.** It would have one live entry, and checking repeatability
  first keeps a wider table away from a call that must not repeat.

## Related

- [ADR-0003](ADR-0003-generated-stubs.md), [ADR-0011](ADR-0011-body-v1.md) (the indicator),
  [ADR-0025](ADR-0025-scheduling-reminders.md) (reminder acks),
  [ADR-0061](ADR-0061-abandoned-call-line.md) (the brain's abandoned-call log line).
- [body-core.md](../modules/body-core.md), [body-rpc.md](../modules/body-rpc.md),
  [body-app.md](../modules/body-app.md), [body-overlay runbook](../runbooks/body-overlay.md).
- Measurements: [deadlines](../readings/rpc-deadlines.md) and
  [abandoned calls](../readings/abandoned-call-remaining.md).
