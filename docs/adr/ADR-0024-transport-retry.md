# ADR-0024: Transport retry / reconnect decorator (Slice 2 refinement)

- **Status:** Accepted
- **Date:** 2026-07-08

## Context

Slice 2 shipped the body's `BrainSeamClient` (the tonic adapter behind the
`body_core::BrainTransport` port) as **thin translation with no retries**. A dropped
stream or a transient reachability failure surfaces straight to the caller, and the overlay
treats a failed turn as terminal. That refinement was deferred at
[ADR-0003](ADR-0003-seam-codegen.md) (addendum) and recorded in the ROADMAP ledger. This ADR
lands it.

The concrete failure the refinement targets: the brain is *briefly* unavailable, because it is
restarting after a model swap, or a momentary loopback blip drops the connection, and a
read the overlay makes (`list_sessions` for the switcher) fails hard when a retry a beat
later would have succeeded. The brain is a supervised local process that comes back within
seconds; a single automatic retry with backoff turns a user-visible error into a hidden
hiccup.

Constraints from AGENTS.md the design must respect:

- **The adapter stays thin.** Retry *policy* is business logic; per the hexagonal rule an
  adapter holds none. So retry cannot live inside `BrainSeamClient`.
- **The core is pure, with no I/O and no OS APIs.** A backoff sleep is a timer effect (an OS
  clock). It cannot be called from `body_core` directly; it must be an injected port.
- **100% line+branch coverage without a network or a wall-clock.** Whatever holds the retry
  loop must be testable deterministically, with no real timers and no real sockets.

## Decisions

1. **Retry is a decorator over the port, not code in the adapter.**
   `RetryingTransport<T: BrainTransport, S: Sleeper>` (in `body_core::retry`) *is* a
   `BrainTransport`: it wraps an inner transport `T` and adds a bounded-retry loop around the
   inner calls. Generic over any `BrainTransport`, so it is exercised in full against a fake
   inner transport with zero network. The real `BrainSeamClient` stays byte-for-byte the thin
   translation it was. Its "no retries" contract is now *true by construction*, with
   resilience composed on top.

2. **Only the idempotent methods are retried.** `health`, `list_sessions`, and
   `session_messages` are read-only (repeating one has no side effect), so they retry on a
   transient failure. **`converse` is pass-through, unchanged.** It is non-idempotent (a turn
   may run tools, stream partial output, mutate session state), its `decisions` argument is a
   one-shot `impl Stream + 'static` that cannot be replayed across attempts, and the overlay's
   contract already treats a failed turn as terminal. The decorator forwards `converse`
   straight to the inner transport and never retries it. (Safe reconnect of `converse` *before
   the first event* is a distinct, harder change. It needs a replayable request and a
   different signature. It stays deferred.)

3. **Transient = `Connection` or `Rpc{Unavailable}`; everything else is terminal.**
   `is_transient` (pure) classifies a `TransportError`:
   - `Connection(_)` → retry. An unreachable brain, or a transport failure before a reply, is
     the clearest "try again" signal (a lazy channel surfaces a down endpoint here).
   - `Rpc { code, .. }` → retry **iff** `code == "Unavailable"`, the gRPC convention for a
     transient backend condition (the session reads already surface a store-down abort as
     `Unavailable`). Every other status (`Internal`, `Unimplemented`, `Unauthenticated`, …) is
     a genuine application answer (a repeat would return the same thing), so it is terminal.
   - `Protocol(_)` → terminal. Malformed wire data will not reinterpret on a repeat.

4. **Bounded exponential backoff, no jitter (v1).** `RetryPolicy` (pure, `Copy`): `max_attempts`
   (total tries incl. the first; `1` disables retry), `base_delay`, `multiplier`, `max_delay`
   (the cap). The delay before retry *k* (0-based) is `min(base_delay · multiplierᵏ, max_delay)`,
   computed by saturating multiply so no overflow escapes the cap. Jitter is omitted from v1:
   it needs a randomness effect (a second injected port), and with a single supervised local
   peer the thundering-herd problem jitter solves does not arise. Recorded as deferred.

5. **A `Sleeper` port makes time an injected effect.** `Sleeper::sleep(&self, Duration) ->
   impl Future + Send` is the one seam the decorator uses to wait between attempts. Tests inject
   a `FakeSleeper` that records the requested durations and returns immediately, so the backoff
   *schedule* is asserted deterministically with no real time elapsing. The real adapter,
   `TokioSleeper` (a one-line `tokio::time::sleep`), lives in the ungated Tauri shell (the
   composition root, host-validated), keeping the timer effect out of the gated crates.

6. **A lazy channel makes the decorator load-bearing for the dial too.** The existing eager
   `BrainSeamClient::connect[_with_token]` fails immediately when the brain is down, so the
   decorator would never get a turn. So `body_rpc` gains
   `connect_lazy_with_token`, which builds the client over tonic's `Channel::connect_lazy`:
   construction only fails on a bad URI or bad token, never on reachability, and each RPC
   (re)establishes the connection on demand. Composed under `RetryingTransport`, a call against a
   briefly-down brain now fails `Connection`, the decorator waits and retries, and tonic
   transparently reconnects when the brain returns. Eager `connect` stays for callers that want
   fail-fast (the live tests, a future health probe that should report "down" rather than block).

7. **Wired for the read path; `converse` unchanged.** The shell composes
   `RetryingTransport::new(connect_lazy_with_token(...), TokioSleeper, RetryPolicy::from_env)` in
   the shared `connect()` used by `list_sessions` / `session_messages`. The policy is
   configurable via env (`CORTEX_BRAIN_RETRY_ATTEMPTS`, `_BASE_MS`, `_MULTIPLIER`, `_MAX_MS`),
   defaulting to 3 attempts / 200 ms base / ×2 / 2 s cap. `converse.rs` keeps its eager dial and
   terminal-turn behavior, which matches decision 2.

## Consequences

- A genuinely-down brain now costs the read path up to `(max_attempts − 1)` backoff waits
  before it surfaces the error (bounded: ≤ 2 × 2 s with the defaults). A deliberate trade of a
  little latency-on-failure for resilience-to-blips; the overlay's `.catch` still renders the
  final error if every attempt fails.
- A brain that (mis)reports `Unavailable` for a non-transient condition will be retried. That
  is the documented gRPC contract for the code, so treating it as transient is correct; a brain
  that wants "do not retry" uses any other status.
- The `Sleeper` port is a new, reusable seam. Any later body-side backoff (reconnect loops,
  poll intervals) injects the same effect and tests against the same fake.
- `converse` resilience is explicitly *not* delivered: a dropped turn stays terminal. The
  overlay's existing "failed turn is terminal" contract is unchanged, so nothing regresses.

**Deferred (behind the unchanged `BrainTransport` / `Sleeper` seams), recorded in the ROADMAP
ledger:** randomized jitter; safe `converse` reconnect-before-first-event (replayable request +
signature change); dial-retry for the *eager* `connect` (the lazy path covers the shell); a
per-method or per-error-code policy; and a retry budget / circuit-breaker if a flapping brain
ever makes blind retries wasteful.

## Addendum (2026-07-13): jitter and the patient eager dial land

Two of the deferrals land together, behind the unchanged `BrainTransport`/`Sleeper` seams.

**Equal jitter over a `Randomness` port.** The randomness effect decision 4 called for:
`Randomness::unit(&self) -> f64` (a value in `[0, 1]`), mirroring `Sleeper` exactly (real
adapter in the ungated shell, deterministic fake in tests). The retry loop scales each
computed delay by `0.5 + 0.5 * unit()` (equal jitter): half the delay stays as a floor,
because this wait's purpose is giving a restarting local brain time to come back, not only
decorrelating a herd, and a zero-floor draw would burn an attempt instantly. The drawn
value is sanitized first (out-of-range clamped into `[0, 1]`, a non-finite draw treated as
the full delay, since `clamp` would otherwise pass a `NaN` through to a panicking
`mul_f64`), so a misbehaving source degrades the spread rather than crashing the loop.
`FullDelay`, the constant-1 source, degenerates the formula to the exact v1
schedule; `RetryingTransport::new` uses it, so existing compositions and the schedule
tests hold unchanged, and `with_randomness` opts a composition in. The shell adapter
(`ShellRandomness`) draws its unit values from `std::collections::hash_map::RandomState`
(std's per-instance random seed), which is jitter-grade spread without a new dependency;
`CORTEX_BRAIN_RETRY_JITTER=off` pins it to 1, restoring the deterministic schedule, and
the default is on.

**The patient eager dial.** The decorator's private retry loop is extracted as a public
`retry_with(policy, sleeper, randomness, call)` helper over any fallible async factory
(the transport's idempotent methods now delegate to it). `converse.rs` composes it around
its eager `connect_with_token`, so a turn started against a briefly-down brain retries the
dial instead of failing on the first refused connect. This is safe precisely because the
non-idempotent turn has not begun until the dial succeeds, so it does not touch decision
2's terminal-turn contract. A permanent misconfiguration (bad URI, non-ASCII token) would
otherwise be retried for the whole budget, since it surfaces as the same `Connection`
error a down brain does, so `converse` first runs the lazy constructor as a synchronous
config gate (it validates URI and token without dialing, the same fast-fail the read path
already gets) and only the reachability dial is retried. `connect_with_token` itself stays
fail-fast (decision 6's callers are unchanged); patience is composed where it is wanted,
never baked in.

Still deferred (ROADMAP ledger): safe `converse` reconnect-before-first-event, the
per-method / per-error-code policy, and the retry budget / circuit breaker.

## Addendum (2026-07-16): the per-method policy lands, and the per-error-code half is audited

The remaining deferral was written as one item, and reading it against the code found two
halves of very different weight. Both are answered here, behind the unchanged
`BrainTransport` / `Sleeper` / `Randomness` seams, which the entry's "behind the existing
seams" claim predicted correctly.

**First, the audit, because it decides what is worth building.** Every RPC on `BrainService`
was classified by whether repeating it can duplicate a side effect or change the answer:
`Health`, `ListSessions`, `GetSessionMessages` and `ListDueReminders` are reads (verified
brain-side: each is a view of a store the handler does not touch, and `list_due_reminders`
maps `ScheduleStore.deliverable()` without marking anything delivered); `Converse` runs a
turn; `AckReminder` writes. Decisions 2 and ADR-0025 already had it right, so **nothing
non-idempotent was being retried**, and the defect this entry might have exposed does not
exist. What did not exist was any *enforcement*: the split was two hand-written `impl`
bodies, and a seventh method added by copying a retried one would have been retried silently.
The backlog already queues write RPCs for this port (session deletion / rename / pinning), so
the copy was going to be made.

The error-code half turned out to have nothing to configure. The brain emits exactly three
statuses on this service: `UNAVAILABLE` (a store or schedule failure, from `server.py`),
`UNAUTHENTICATED` (the seam-token interceptor, ADR-0016), and the `UNIMPLEMENTED` of the
generated servicer's default, which no implemented method can reach. `is_transient` already
classifies all three correctly, and a configurable retryable-code table would have exactly one
live entry. It is declined for want of a producer and recorded as fix-when-it-bites, with the
trigger named: a brain that starts answering `RESOURCE_EXHAUSTED` or `ABORTED`.

**Decisions.**

1. **Repeatability is a named, exhaustive property of the method** (`retry::plan`).
   `SeamMethod` names all six port calls and `repeatable()` classifies each in one exhaustive
   `match`, so a new variant does not compile until someone decides. `AckReminder` is the
   instructive case and its `false` is unchanged in effect but now carries its reason: the
   brain's `ack` is idempotent, so a repeat does no damage, but an ack whose reply was lost
   has already cleared the reminder, so the retry answers `false` about a reminder this very
   call dismissed. Repeatability is therefore two tests, not one: no duplicated effect **and**
   no changed answer.

2. **`RetryPlan::policy_for` is the one door, and it can say no.** It returns
   `Option<RetryPolicy>`: a schedule for a repeatable method, `None` otherwise. The decorator
   routes every unary call through it, running the retry loop on the resolved schedule or on
   `RetryPolicy::ONCE` (one attempt, no wait) for a `None`, so `ack_reminder` is now unretried
   *by the gate* rather than by bypassing the retry path. A refusal deliberately runs the same
   loop a permission does rather than short-circuiting past it: the first shape of this change
   branched to a direct call on `None`, which left the loop monomorphized for the ack's return
   type and never executed, an uncovered path reachable only by a refused call. A refused call
   must not take a route only a refused call can reach. The
   order of the two questions is the point: repeatability (a fact about the call) is asked
   before transience (a fact about the failure). A status says the brain could not serve the
   call; it never says the brain did not already run it, which is why `is_transient` is
   documented as necessary and never sufficient. `converse` still cannot reach the gate at
   runtime (a stream is not a future the loop can re-issue) and is classified anyway.

3. **The schedule is per method, because the `Health` probe has a different consumer.**
   The connection indicator (ADR-0011 addendum) renders a probe's answer, and the probe *is*
   the reconnect attempt, so patience there is time the dot spends claiming a state the seam
   has stopped proving. `RetryPlan` therefore carries `reads: RetryPolicy` plus a
   `probe_budget: Duration`, and the probe runs `reads.within(probe_budget)`: the same delays
   with the attempts trimmed until the total fits. Trimming rather than rescaling keeps the
   early waits long enough for a restarting brain; what it drops is a tail the indicator could
   not spend honestly. One attempt always survives, so a budget buys back patience, never the
   call. `CORTEX_BRAIN_PROBE_BUDGET_MS` (default 1 s) configures it, and at the shipped
   defaults it does not bind (worst case 600 ms), so **behaviour is unchanged out of the box**;
   what it removes is the ability to make the indicator lie by raising
   `CORTEX_BRAIN_RETRY_ATTEMPTS` for the reads' sake.

**Consequences.**

- The overlay's indicator now has a bound, not a hope. Whatever the read knobs say, `Down`
  arrives within `probe_budget` of the probe starting, and the states themselves are
  unchanged: a refused dial is still `Down`, an answered `Unauthenticated` still `Degraded`
  and still immediately, since it is not transient and never enters the loop.
- `RetryingTransport::new` / `with_randomness` take `impl Into<RetryPlan>`, so every existing
  composition that passes a `RetryPolicy` keeps compiling and keeps its behaviour.
- The gate is only as strong as the enum: adding a port method does not *force* a `SeamMethod`
  variant, it forces the author to pass one, and picking a wrong existing variant is a lie
  rather than an accident. That is the realistic ceiling without a macro over the trait.
- The `converse` dial keeps using `retry_with` directly with the read policy. A dial is not a
  seam method and has no plan entry: it is retried because the turn has not begun, which is
  decision 2's own reasoning, not the gate's.

Still deferred: safe `converse` reconnect-before-first-event (unchanged: it needs a replayable
request and a signature change), the retry budget / circuit breaker, and now the retryable-code
table above, all recorded in `docs/refinements/index.md#seam-transport`.

## Addendum (2026-07-16): safe `converse` reconnect-before-first-event, sharpened and deferred

The last capability this deferral names, resilience for `converse` itself, was audited against
both sides of the seam and kept deferred, now with its blocker and its trigger named rather than
left as "a replayable request and a signature change".

**The effect timeline, read against the code.** A `converse` turn begins its durable side effect
before the client can observe any event, and independently of whether the client reads one. On the
brain a `UserTurn` client event is pumped straight into an independent turn task (`converse.py`:
`_pump` calls `_enqueue_turn`, which calls `_start_next_turn`, which creates `_turn_task`), whose
events land on an internal queue the consumer drains separately, so the turn advances whether or
not the client is reading. That task runs `TurnEngine.handle_turn`, whose first statement after
minting a server-side `turn_id` is `await self._store.append(session_id, user)` (`engine.py`): the
user message is persisted before inference starts and before the loop yields its first `TextDelta`,
`ToolActivity`, or `StatusUpdate`. Persisting the user turn before inference is a deliberate
contract (`test_backend_failure_surfaces_typed_after_user_was_persisted` pins it), not an accident
to reorder. So "the client observed no event" never implies "the brain did no work": by the time a
first event could arrive, the user message is stored and a tool the model asked for first may
already have run.

**No request identity exists on the wire today.** `ClientEvent` and `UserTurn` (`proto/body.proto`)
carry a `session_id`, text, and images, and nothing else: no request id, no client turn id, no
idempotency key. The `turn_id` is minted server-side (`engine.py`, `self._turn_id_factory()`), so
two `converse` calls with the same `session_id` and text are two independent turns. A naive
reconnect-before-first-event that re-issues the request therefore double-runs the turn: a second
`store.append` of the same user message (verified live over the real engine, a resend leaves two
identical user messages under two distinct server-minted turn ids) plus a second full inference pass
that re-dispatches any tools the first pass already ran. That is a correctness regression, worse
than the missing feature, which is why the retry gate classifies `SeamMethod::Converse` as not
repeatable and forwards the stream unretried.

**Why "before the first event" does not rescue it.** The window the entry hoped was safe (request
sent, no event seen) is exactly the window in which the append has already happened. Making the
append observably not-yet-done would mean delaying it past the first event, which reverses the
"persist the user message before inference" contract and still would not cover a tool that runs
before the first text delta. There is no cheap reordering that makes an unkeyed resend safe.

**The exact protocol change a safe version needs.** Either a client-generated request id (a new
field on `UserTurn` or `ClientEvent`, a proto change regenerating both stubs) that the brain dedups
on, or a resumable stream cursor the client presents on reconnect. Both require server-side state
that must survive a brain restart or model swap (the one hard rule), so the dedup or resume registry
lives in the hot store (Redis) keyed by `(session_id, request_id)`, recording each turn's lifecycle
(begun, streaming, complete) and either replaying a completed turn's terminal outcome or
re-attaching a reconnecting client to an in-flight turn's output. Re-attaching means the emitted
events themselves must be buffered in a store both connections can read, a second store-backed
structure. This is a turn-lifecycle state machine plus an idempotency store plus an event replay or
rejoin path: a multi-part protocol and state change, and it reverses the deliberate design that an
in-flight turn is disposable and its partial reply is dropped (`converse.py` and `engine.py`
docstrings both state it).

**Decision: fix when it bites, with the trigger named.** At personal scale the client and brain
share one machine over loopback, reconnects are rare, and the overlay already treats a dropped turn
as terminal (the user resends), so the cost of the safe mechanism is disproportionate to the value.
The trigger that would justify building it: mid-turn brain evictions becoming routine once the real
model swap lands (the model-manager work), and turns long or expensive enough that silently
re-running one on resend is worse than paying for dedup. Until then `converse` stays unretried and
the sharpened entry moves to fix-when-it-bites in `docs/refinements/index.md#seam-transport`.
`SeamMethod::Converse` is unchanged: this is not a path that flips it to repeatable, it is the
reason it is not.

## Addendum (2026-08-17): the retryable-code table is decided, and it stays one entry

The last error-code deferral is answered here rather than deferred again. Decision 3's set
(`Connection`, plus `Rpc{Unavailable}`) is now the **decided** table and not a placeholder
waiting for a producer, and the two candidate widenings the deferral named are argued down
individually.

**The producer sweep, re-run against the code.** Every status this seam's server can write is
still one of two: `UNAVAILABLE` from a store, schedule, memory or preference failure
(`session_servicer.py`, `preference_servicer.py`, `server.py`), and `UNAUTHENTICATED` from the
seam-token interceptor (`auth.py`), plus the `UNIMPLEMENTED` of a generated default no
implemented method reaches. No handler writes `RESOURCE_EXHAUSTED` or `ABORTED`, nothing on the
body's side of the seam sets a deadline, so `DEADLINE_EXCEEDED` cannot arrive either. The one
`RESOURCE_EXHAUSTED` anywhere in this repo is raised by the **body's** `BodyService` for a
screen capture too large to send (`body/crates/rpc/src/screen.rs`) and consumed by the brain as
a client (`failures.py`), which is the opposite direction from the policy this decision governs.

**Why the codes are each terminal, not merely unproduced.** `RESOURCE_EXHAUSTED` is the
instructive one: the single producer on either direction of this seam pair raises it about the
*payload*, and a repeat sends the same payload, so the conventionally retryable reading of the
code would be exactly wrong here. `ABORTED` is a store-contention convention no handler
performs. `DEADLINE_EXCEEDED` is unreachable while nothing sets a deadline, and is the classic
load amplifier once one exists. Each would ship as a guess about a failure nobody has observed,
and a wrong guess costs a duplicated wait on every real failure. They are pinned terminal by
test (`the_codes_a_wider_table_would_have_added_are_still_terminal`), so widening the set is a
decision someone makes deliberately rather than a line that drifts in.

**Why the idempotency hazard cannot arise, which is what makes the small table safe.** The
usual danger in a retryable-code table is that a code judged transient reaches a call that must
not repeat. That cannot happen here, and not by care: the per-method addendum above made
repeatability the *first* question. `RetryPlan::policy_for` refuses an unrepeatable method
before any error exists, and the decorator runs the refusal on `RetryPolicy::ONCE`, so no status
this classifier could ever be taught reaches `Converse`, `AckReminder`, or any catalog write.
The code table is therefore a pure question about the failure, and a future widening is a
one-line change that cannot become a correctness bug, which is the strongest possible reason
not to build configuration for it now.

**Consequences.** `is_transient` is unchanged, so no behaviour changes. What changed is that
the classification is now argued for every code a widening would have added and pinned by a
test that fails when the set grows, and that the gate's whole-port invariant covers the whole
port: `EVERY_METHOD` still called itself every variant while listing nine of eleven, so
`GetPreferences` and `SetPreference` sat outside the invariant and outside the explicit
repeatability assertions. Both are named now. A future producer reopens the classification for
that code alone, against what the producer means by it.

## Addendum (2026-08-18): a per-attempt deadline, enforced in the core and never retried

Every duration this decision has spent so far bounds the wait *between* attempts. Nothing bounded
an attempt, so the whole design assumed a brain that answers or fails and had nothing to say about
one that accepts the connection and then goes quiet. The consequence recorded above, that `Down`
arrives within `probe_budget` of the probe starting, held only for a brain that answers. The
harm is not theoretical at the far end either: the overlay's `useLink` holds an `inFlight` latch
that is cleared in the promise's `finally`, so one probe that never resolves disables every later
probe forever and the 5 s recovery interval fires into a no-op for the rest of the session
(`body/app/src/overlay/useLink.ts`). An unbounded attempt does not merely delay one answer, it
ends the indicator.

**The obvious shape is a trap, and reading tonic is what found it.** The natural implementation is
`Endpoint::timeout` or `Request::set_timeout`, letting tonic expire the call. In tonic 0.14 an
expired client-side timeout is `TimeoutExpired`, and `find_status_in_source_chain` turns that into
`Status::cancelled("Timeout expired")` with **no source attached** (`tonic/src/status.rs`). The
adapter's classifier keys on finding a `tonic::transport::Error` in the source chain
(`body/crates/rpc/src/status.rs`), so a sourceless status is by construction the "the brain
answered" case: the body's own expired deadline would arrive as `TransportError::Rpc { code:
"Cancelled" }` and the indicator would draw `Degraded`, which claims the brain replied. A deadline
built that way would report the hang as an answer, inverting the one signal it exists to make
honest, and it would look like it worked.

**So the deadline is enforced in the core, over the port that already owns the clock.** `Sleeper`
gains a second method, `bounded(deadline, call) -> Option<T>`, where `None` means the deadline won
the race and the call was dropped (which for the gRPC adapter resets the in-flight stream, so an
abandoned attempt stops costing the brain). `sleep` is the wait between attempts and `bounded` is
the bound on one attempt: the same effect, asked two ways, and the core keeps the *policy* (how
long) while an adapter keeps the *clock*. The real implementation is one line of
`tokio::time::timeout` in the ungated shell beside `TokioSleeper::sleep`, exactly as decision 5
placed the timer; the fakes grant or expire a call outright, so the decorator's behaviour under a
deadline is tested with no wall clock. `retry::deadline::within_deadline` is the composition the
decorator applies around every attempt, and it is public so the shell wraps its eager `converse`
dial in it too: with that, no call the body makes on this seam is unbounded, the dial included.

**The expiry is its own failure, not a status.** A new `TransportError::Timeout { after }` carries
the deadline that expired. It is a fourth variant rather than a reuse of `Connection` or `Rpc`
because it is genuinely a fourth thing: `Connection` is "nothing accepted the call", `Rpc` is "the
brain answered", and a timeout is "we stopped waiting", which neither of the others can say
without lying. `LinkStatus::from_error` draws it `Down`, because `Degraded`'s defining property is
that the brain answered and a timeout is precisely the absence of an answer; the detail line says
`no reply within 250ms`, so the tooltip still separates a wedged brain from an absent one. The
variant also unifies a race that would otherwise show two dots for one event: once the courtesy
`grpc-timeout` header lands, the same expiry can arrive locally or as the brain's own
`DEADLINE_EXCEEDED`, and both mean the same thing to everything above the adapter.

**Two deadlines, because the consumers differ, and one method has none.** `RetryPlan` carries
`probe_deadline` (`DEFAULT_PROBE_DEADLINE` = 250 ms) and `call_deadline` (`DEFAULT_CALL_DEADLINE`
= 5 s), resolved by `deadline_for(method)` the way `policy_for` resolves the schedule. The probe's
number is defensible from the handler it calls: brain-side `Health` is documented synchronous and
lock free precisely so a probe cannot queue behind the swap it reports on, and on loopback it
answers in single-digit milliseconds, so 250 ms is two orders of magnitude of headroom and
anything past it is a brain the indicator should stop vouching for. The reads and the catalog
writes are store operations on loopback, so 5 s is far beyond a healthy one and still short enough
that the switcher admits failure while the user is watching. `Converse` gets `None`: a turn is
long by design, and a clock is the wrong thing to end one. `within_deadline` spells that `None`
as `Duration::MAX` instead of branching on it, which is what an absent deadline means to a clock
and which keeps a dead arm out of generic code that is compiled once per call type. Note that the writes are bounded though
they are never retried, which is the point worth keeping: bounding is not repeating, so
repeatability and a deadline are independent questions and every unary call gets an answer or a
`Timeout`.

**The probe budget now counts the attempts, which is what makes its promise true.** `within` took
a budget and trimmed attempts until the *backoff* fit; an attempt that can cost up to a deadline
makes that arithmetic wrong, since a slow attempt that fails transiently spends its deadline and
then buys a wait. It now takes the per-attempt cost too and trims until
`attempts × deadline + backoff` fits, so the bound the indicator advertises is real:
**`Down` arrives within `max(probe_budget, probe_deadline)`**, one attempt always surviving, and
the first half of that max holds whenever a single attempt fits the budget at all. This does
change the shipped default, and deliberately: at 250 ms per attempt the probe keeps 2 attempts
rather than 3 (250 + 200 + 250 = 700 ms fits the 1 s budget, adding a third does not), so the dot
resolves inside 700 ms worst case and still spends one real retry on a restarting brain. The read
schedule is untouched.

**A timeout is terminal, and this is the decision the entry existed to make.** The retryable set
is unchanged: `Connection` and `Rpc{Unavailable}` retry, and `Timeout` joins `Protocol` and every
other status as terminal. Three reasons, in the order they decided it. First, a retried deadline
is the classic load amplifier, and it amplifies exactly when the system is least able to take it:
the condition that produces a timeout is a brain too slow or too stuck to answer, and the response
of issuing the same call again two more times is the worst available. Second, and this is the
argument that is specific rather than conventional, a timeout is not the brain's report about the
call, it is *our own decision to stop waiting*. `Unavailable` is an answer that invites a retry,
because the brain is saying it could not serve this one; a timeout says nothing whatever about the
brain, and in particular it cannot say the next attempt will be faster. The cure for a call that
needs longer is a longer deadline, which is a knob, not a repeat. Third, the abandoned attempt may
still be running brain side, so a retry stacks a duplicate on a peer that is already too slow to
answer the first. The earlier decline of `DEADLINE_EXCEEDED` rested on there being no producer;
that ground is gone now, and the classification stands on its merits instead, which is why the
pinning test names both the code and the new variant.

**Consequences.**

- No attempt the body makes on this seam is unbounded: the decorator bounds every unary call, and
  the shell bounds its `converse` dial with the same helper. The turn stream itself is
  deliberately outside that, since ending a turn on a clock is a different decision with a
  different consumer.
- The indicator's bound is now arithmetic rather than hope, and `Down` is what a hang draws. The
  overlay's `inFlight` latch is released on every path, so the recovery cadence survives a wedged
  brain.
- The default probe spends 2 attempts instead of 3. Raising `CORTEX_BRAIN_PROBE_BUDGET_MS` or
  lowering `CORTEX_BRAIN_PROBE_DEADLINE_MS` buys the third one back; neither can make the dot
  claim a state the seam stopped proving, because the trim is computed from both.
- `CORTEX_BRAIN_PROBE_DEADLINE_MS` (default 250) and `CORTEX_BRAIN_CALL_DEADLINE_MS` (default
  5000) join the retry knobs in the shell, parsed the same way.
- A brain that is merely slow now fails a read at 5 s where it used to hang, which is a behaviour
  change for anyone whose store is slower than that. The knob is the answer, and the failure is
  typed rather than silent.

Still deferred, recorded in `docs/refinements/index.md#seam-transport`: the courtesy `grpc-timeout`
header, so the brain learns the deadline and abandons its own work rather than finishing a reply
nobody is waiting for. It is a separate slice because it touches the adapter's client construction
(the interceptor is the natural place to set it) and because classification must never come to
depend on tonic's own expiry, which is what the first paragraph above rules out. Safe `converse`
reconnect before the first event is unchanged, and so is the retry budget / circuit breaker.

## Addendum (2026-08-18, later): the retry budget and circuit breaker are declined, not deferred again

Every "Still deferred" line above names a retry budget or a circuit breaker, carried from the
original decisions to the deadline addendum an hour before this one. It is closed here on the
merits, on a reading of the tree rather than on the reasoning that first deferred it, and the first
thing that reading found was that this ADR's own cost estimate for it, "behind the unchanged
`BrainTransport` / `Sleeper` seams", is wrong.

**No producer.** The transient set is `Connection` and `Rpc{Unavailable}` and nothing else, an
expired deadline is terminal, and only the five repeatable reads reach the loop. The shipped
schedule is 3 attempts with a 200 ms base, and the probe trims its attempts to the budget the
indicator renders. Nothing on the body polls: the overlay probes on summon and re-checks only while
it is visible and the link is not ready, single-flighted, the liveness poll having been rejected in
`useLink.ts` for its own reasons. So a flapping brain costs at most two extra connect attempts per
user action, against a supervised local process on loopback that refuses a connect instantly. A
breaker is a load-shedding device for a shared or remote peer with many clients, and this seam has
one client, one user, and one process at the other end.

**Two seam changes, not none.** A breaker holds state across calls, and the shell builds a fresh
transport per IPC command through `seam::connect()`, so anything kept inside `RetryingTransport`
dies with the call that made it; the state would have to become process-lifetime shell state. Its
open-to-half-open transition then has to read a clock, and `Sleeper` can only wait or bound an
attempt. A clock-reading port would be new, with the fake and the adapter that go with it.

**It would also make the indicator lie.** A call refused by stale open state reports a seam state
nobody asked the brain about, which is precisely what the probe budget and the per-attempt deadline
were built to rule out. The one genuinely unbounded cost this seam had was a brain that accepts a
connection and then goes quiet, and that is what the deadline addendum above closed.

**What would reopen it**, and each is a new entry rather than this one resumed: a background poller
on the body, so retries pile up while nobody is watching; `CORTEX_BRAIN_ADDR` aimed at a brain that
is not a supervised loopback process; or a blind retry that starts costing seconds rather than
microseconds, which is what either of those would make of it. The record and the re-derivation live
in [docs/refinements/index.md#seam-transport](../refinements/index.md#seam-transport).
