# body/crates/core: retry and deadlines (`body_core::retry`)

**Purpose.** The bounded-retry and deadline layer over the `BrainTransport` port (ADR-0024). It is a
decorator, so the gRPC adapter stays thin and the logic is exercised against a fake with no network
and no wall clock. The port itself, and everything else in this crate, is in
[body-core.md](body-core.md). ADR-0024 holds the reasoning for each rule below.

- `Sleeper` (`retry::effects`) is the timer port, asked two ways: `sleep(&self, Duration)` for the
  backoff *between* attempts, and `bounded<F>(&self, deadline, call)` for the deadline *on* one
  attempt, `None` meaning it expired first and the call was dropped. Both are the same clock, so it
  is one port. The real `tokio::time` calls live in the shell.
- `Randomness` is the jitter port: `unit(&self) -> f64`, one draw in `[0, 1]` per backoff. The retry
  loop scales each delay by `0.5 + 0.5·unit()`, half kept as a floor so the wait still lets a
  restarting brain recover, and `FullDelay` returns a constant `1.0`, which turns jitter off. A draw
  is sanitized (clamped into `[0, 1]`, a non-finite draw treated as the full delay).
- `RetryPolicy` (`retry::policy`) is a bounded exponential-backoff schedule: `max_attempts` (total
  tries including the first, where `0` and `1` disable retry), `base_delay`, `multiplier` and
  `max_delay`. `delay(index)` is `min(base · multiplier^index, max_delay)`, saturating;
  `backoff(attempt, error)` returns the wait to apply or `None` to give up, retrying only while an
  attempt remains *and* the error is transient. `Default` is 3 attempts, 200 ms, ×2, 2 s cap.
  `worst_case_backoff()` sums every wait the schedule can spend, unjittered since equal jitter only
  shortens a wait. `within(budget, attempt)` trims attempts until `attempts × attempt + backoff`
  fits `budget`, leaving the delays alone, and one attempt always survives, so the guarantee is
  `attempts × attempt + backoff ≤ max(budget, attempt)` (decision 10). `RetryPolicy::ONCE` cannot
  retry and is what a non-repeatable method runs on.
- `is_transient(&TransportError) -> bool` is the retryable classifier: `Connection` and
  `Rpc{code=="Unavailable"}` are transient; every other `Rpc` status, `Protocol` and `Timeout` are
  not. **`Timeout` is terminal by decision** (decision 13), and being transient is **necessary** for
  a retry and never sufficient, since a status says the brain could not serve the call, never that
  it did not already run it. Widening that one-entry set is safe one code at a time, because
  `policy_for` has already excluded every call with an effect (decision 3).
- `SeamMethod` (`retry::plan`) names every `BrainTransport` method, and `repeatable()` is the safety
  property retry rests on: **repeating the call is observably the same as making it once**. It is
  true for the reads and false for `Converse`, for `AckReminder`, whose *effect* is idempotent
  brain-side but whose *answer* is not, and for the three catalog writes. `AckReminder` shows that
  repeatability is two tests rather than one: no duplicated effect **and** no changed answer. The
  match is exhaustive, so a new variant does not compile until it is classified.
- `RetryPlan` (`retry::plan`) says which schedule and which deadline each method runs under: `reads`
  (the `RetryPolicy` for the repeatable reads), `probe_budget` (the ceiling a `Health` probe's whole
  run is trimmed to, attempts and backoff together, `DEFAULT_PROBE_BUDGET` = 1 s), `probe_deadline`
  (`DEFAULT_PROBE_DEADLINE` = 250 ms), `call_deadline` (`DEFAULT_CALL_DEADLINE` = 5 s) and
  `turn_gaps`. One constant beside them is not a field and not configurable,
  `ANNOUNCED_DEADLINE_GRACE_MS = 250`. The probe is budgeted separately because the connection
  indicator renders its answer: at the defaults the budget leaves it two attempts (250 + 200 + 250
  fits 1 s, a third would need 1.35 s) while the reads keep all three.
- **Three entry points decide everything, one per question.** `policy_for(method)` answers `None`
  for a method that may not be repeated at all, and the caller must then make exactly one attempt
  and report whatever comes back, however transient it looks. `deadline_for(method)` answers `None`
  for `Converse` alone, a turn being long by design, and a duration for every other call, **the
  writes included**, since bounding a call is not repeating it (decision 11). `gaps_for(method)` is
  the mirror, `Some` for `Converse` alone. Between the last two, **every call on the port is
  bounded, by a clock on the call or a clock on its silence, and never by both**, which
  `retry_plan.rs` asserts over every variant.
- `TurnGaps` (`retry::gap`) is that pair: `first`, the longest silence allowed before a turn's first
  event (`DEFAULT_TURN_FIRST_GAP_MS = 600000`), and `idle`, the longest between two events
  (`DEFAULT_TURN_IDLE_GAP_MS = 14400000`). `TurnGaps::UNBOUNDED` is both at `Duration::MAX`. **The
  idle one is the longer, and that is not a typo**: the first is the sum of the brain's own bounds
  on a swap and a first token, while the mid-stream one has to clear a delegated subtask waiting for
  admission and then running (decisions 19 and 20).
- `announced_deadline_for(method)` is what the body **tells the brain** a call will be waited on,
  which the gRPC adapter sends as `grpc-timeout` so a brain still working on an abandoned call
  learns it has been (decision 15). It is `deadline_for` plus the grace, never equal to it, and
  `None` wherever `deadline_for` is. The header also starts the transport's own clock, and an expiry
  the transport enforces classifies `Connection`, which is *retryable*, so the announcement must be
  the later of the two clocks by construction. What sizes the margin is the scheduler stall the
  ordering must survive. `retry_plan.rs` checks it over every method.
- `within_deadline(deadline, sleeper, call)` (`retry::deadline`) is what the decorator wraps around
  every attempt: the call's own result when it finished in time, and
  `TransportError::Timeout { after }` when it did not. A `None` deadline is written as
  `Duration::MAX` rather than branched on, this being generic code where a branch is compiled once
  per call type with the unbounded side dead in every copy. The bound lives here rather than in the
  adapter because tonic classifies its own expiry as `TransportError::Connection`, which is
  *retryable*; enforced here it arrives as `Timeout`, which is terminal (decisions 13 and 14).
- `within_gaps(gaps, sleeper, stream)` (`retry::gap`) is the same composition for a stream: items
  pass through untouched and only the **silence between them** is bounded, so a turn that keeps
  talking is never cut off. The first item is measured against `gaps.first` and every later one
  against `gaps.idle`. An expired gap yields one final `TransportError::Timeout { after }` naming
  the gap and ends the stream, dropping the inner one, which cancels the turn. Ending it with no
  error was rejected: the overlay leaves a reply streaming until a terminal event or an error
  reaches it.
- `retry_with(policy, sleeper, randomness, call)` is the bounded-retry loop over any fallible async
  factory (decision 7): it re-issues `call()` each attempt, sleeping the jittered delay while
  `backoff` says so. It executes the schedule rather than deciding it, and relies on the caller
  having established that repeating `call` is safe. It and `within_deadline` are public so both
  compose around a non-transport future, which the shell's eager dial uses.
- `RetryingTransport<T: BrainTransport, S: Sleeper, R: Randomness = FullDelay>` *is* a
  `BrainTransport`: it wraps an inner transport and routes every unary call through the plan's
  answer for that `SeamMethod`, running `retry_with` on the resolved schedule when the method is
  repeatable and on `RetryPolicy::ONCE` when the plan allows no retry, so a non-repeatable call
  makes **exactly one attempt**. `converse` cannot reach that decision at runtime, a stream not
  being a future the loop could re-issue; it is classified all the same so the port's methods are
  covered exhaustively, and its items are forwarded as they arrive under the plan's `TurnGaps`
  (decisions 2 and 18). `new(inner, sleeper, plan)` is the no-jitter default and
  `with_randomness(inner, sleeper, randomness, plan)` the jittered one; both take
  `impl Into<RetryPlan>`, so a bare `RetryPolicy` still works.

