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

**The obvious shape is a trap, though not where reading tonic first said it was.** The natural
implementation is `Endpoint::timeout` or `Request::set_timeout`, letting tonic expire the call. In
tonic 0.14 an expired client-side timeout is `TimeoutExpired`, and it reaches the caller as
`Status::cancelled("Timeout expired")` carrying the originating `tonic::transport::Error` on its
source chain. The adapter's classifier keys on finding exactly that
(`body/crates/rpc/src/status.rs`), so the body's own expired deadline would arrive as
`TransportError::Connection` and the indicator would draw `Down`, which is the honest reading of a
call nothing answered. What it would also be is **retryable**: `Connection` is in the transient set
(decision 3), so a tonic-armed deadline would be retried, which is precisely the load amplifier the
retryability section below rules out, reached through a back door and looking like it worked.

> **Corrected 2026-08-18.** As first written this paragraph claimed the expiry arrives *sourceless*
> and therefore classifies `TransportError::Rpc`, drawing `Degraded` and claiming an answer that
> never came. That was read out of tonic's source, and it is false. The measurement, how the read
> went astray, and why the conclusion survives it are in the correction addendum below.

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

## Addendum (2026-08-18, later still): tonic's own expiry was misread, and a test now holds the answer

The deadline addendum above opened on a claim about tonic that was reached by reading tonic's
source and never by running it. The claim is false. It is corrected here rather than quietly
edited away, because a correction that leaves no trace teaches nothing and the next agent will
re-derive the same mistake from the same code.

**What the record said.** That an expired client-side timeout arrives as a *sourceless*
`Status::cancelled`, so `status_to_error` would classify the body's own deadline as
`TransportError::Rpc { code: "Cancelled" }` and the indicator would draw `Degraded`, claiming an
answer that never came. The same sentence had been restated in the two backlog task files, in the
`body_core` and `body_rpc` module docs, in the `retry::deadline` module comment, and twice on the
other side of the seam, where the Python body client cited it as the shape it was glad not to
have.

**How the read went astray, which is the part worth keeping.** Every step of it is true about the
function it looked at. `find_status_in_source_chain` (`tonic/src/status.rs`) really does answer a
`TimeoutExpired` with `Some(Status::cancelled("Timeout expired"))`, and that status really is
built with `source: None`. The reading stopped at the `return`. Two lines after the call site, in
`Status::try_from_error`, the caller writes `status.0.source = Some(err.into())` on whatever that
helper handed back, so every status minted there gets the originating error attached before any
caller sees it. On a channel call that error is the `tonic::transport::Error` wrapping the
expiry, which is exactly what the adapter's classifier hunts for.

**How it was disproved: by running it.** A throwaway probe drove a raw `BrainServiceClient`
against the existing `Script::Hanging` fake brain (which accepts the connection and never
answers), armed `Request::set_timeout`, and walked the resulting status's `source()` chain:

```
PROBE code=Cancelled msg="Timeout expired" elapsed=81.302086ms has_transport_source=true chain=["transport error", "Timeout expired"]
```

So the true classification is `TransportError::Connection("transport error: Timeout expired")`,
and `LinkStatus::from_error` draws it `Down`. The indicator would have been accidentally honest.

**The conclusion stands, on a different and worse hazard.** `Connection` is in the transient set
(decision 3), so an expiry tonic enforced would be **retried**, two more times on the shipped
schedule, against a peer that has just proved too slow or too stuck to answer. That is the load
amplifier the retryability section above declines on the merits, arrived at through a back door
and, unlike the misread version, arrived at *silently*: nothing in the indicator would look wrong
while it happened. Two smaller reasons survive alongside it. `Connection`'s contract is "nothing
accepted the call", which is not what an expiry means, and folding the two loses the distinction
the tooltip renders. And `TransportError::Timeout { after }` carries the deadline that expired,
which a `Connection` string cannot. So the deadline stays in the core over the `Sleeper` port,
`Timeout` stays terminal, and nothing in the shipped design changes.

**Pinned rather than asserted.** `tonics_own_expired_timeout_classifies_as_a_retryable_connection_failure`
(`body/crates/rpc/tests/client.rs`) now runs the probe as a permanent, CI-safe check: it drives a
real expiry against the hanging fake, asserts the code is `Cancelled` (the half the original
reading got right), asserts the classification is `Connection` and draws `Down`, and asserts
`is_transient` says yes, which is the hazard. It fails on either side of the claim: replacing the
real status with the sourceless one the record described makes it panic with
`Rpc { code: "Cancelled" }`, and a tonic upgrade that stops attaching the source fails it the same
way. `status_to_error` is now `pub` for that test, which is the only code change here.

**One measurement the correction turned up, which the courtesy-header follow-up needs.**
`Request::set_timeout` does not arm a timer of its own: it only inserts the `grpc-timeout`
metadata (`tonic/src/request.rs`). The client channel's own `GrpcTimeout` layer then parses that
header back off the outgoing request and arms the local clock from it
(`tonic/src/transport/service/grpc_timeout.rs`), which is why the probe above expired locally.
Announcing the deadline to the brain and arming a tonic timer on the body are therefore **the same
act** in tonic, not two choices. A courtesy header cannot be added without a local timer coming
with it, so the follow-up has to make sure the core's bound wins that race deterministically
rather than by luck.

**The rule this is an instance of.** A claim about a dependency's behaviour is a measurement, not
a reading. Reading names the mechanism and is how you know what to measure; it does not establish
what happens, because the frame above the one you read can undo it. Where a claim decides a
design, the run belongs in the record, and better, in a test.

## Addendum (2026-08-19): the courtesy `grpc-timeout` lands, a grace margin ahead of our own clock

The deadline addendum above left the brain unable to see the bound it was being held to: the body
enforced a per-attempt deadline, dropped the call when its clock won, and put nothing on the wire
saying how long it had meant to wait. The header for exactly this exists, so it is sent now. What
made this a slice rather than a line is the constraint the correction addendum turned up, that
announcing a deadline and arming tonic's own clock are the same act, and the design is built around
losing that race deliberately.

**Announce longer than you enforce, by a named margin.** `RetryPlan` grows a second question next
to `deadline_for`: `announced_deadline_for(method)`, which is the enforced deadline plus
`ANNOUNCED_DEADLINE_GRACE_MS` (250 ms), and `None` for `Converse`, which has no deadline to
announce. That ordering is what makes the race deterministic rather than lucky. Both clocks start
on the same runtime, ours strictly first (the `bounded` timer is armed before the call future is
polled, and tonic's `GrpcTimeout` layer only sees the request after that), so a strictly longer
announcement cannot fire first. The margin pays for three things, in ascending order of size: a
loopback round trip plus the brain's own header parse, which is about a millisecond; the header
encoding's truncation to whole units, which on tonic's ladder is under a microsecond for any
announcement below 100 s and exactly zero for both values the shipped plan produces; and, the one
that actually sizes it, the scheduler slack the ordering has to survive, since a runtime stalled
past *both* deadlines would find them both due in one poll and `tokio::time::timeout` polls the
call before the clock. A quarter second is far beyond any stall this runtime should have, and it
is bounded above by its own purpose: the brain works at most that long past the moment the body
stopped waiting. (The first two of those three were sized by reading rather than by measuring, and
the encoding addendum below measured both; the margin is unchanged and the sentence is not what it
was.)

**Where the per-call value enters.** The interceptor is the only place every outgoing request
passes through, and it is built once per client, so the client had to gain a way to carry a
per-call deadline into it. Of the shapes considered, the client now holds the channel, the token
and the plan, and builds the generated client per call (`SeamCall`, `body/crates/rpc/src/call.rs`,
which took the interceptor and the `SEAM_TOKEN_HEADER` declaration with it under the line cap).
Threading a duration through every translation helper was the alternative and would have put the
same number in four modules' signatures; a tonic `Extensions` value on each request reaches the
interceptor too, but the request is built inside those same helpers, so it is the same threading
wearing a different hat. Holding the plan also answers the reply side, which the header alone
cannot: `SeamCall` carries what it announced, so a brain-sent `DEADLINE_EXCEEDED` maps to
`TransportError::Timeout { after }` naming the announcement that expired. The seam token now lives
in a struct the client owns, so `Debug` is written out and redacts it rather than being derived.

**The classification did not move, and that is the point.** tonic's own expiry still carries a
`transport::Error` and still classifies `Connection` (retryable);
`tonics_own_expired_timeout_classifies_as_a_retryable_connection_failure` is unchanged and still
green, and a new unit check pins that an *announced* call does not move it either. The only new
answer is for a status the brain sent, and only on a call that announced something: without an
announcement there is no deadline of ours that expired and nothing honest to put in `after`, so it
stays `Rpc{DeadlineExceeded}`, which is terminal too. Nothing about a retry decision turns on
which of the two it is.

**One refusal, for a panic this would otherwise have introduced.** `grpc-timeout` carries at most
8 digits, and tonic's encoder walks its unit ladder and then panics (`expect("duration is
unrealistically large")`). `RetryPlan`'s fields are public and its millisecond knobs are `u64`, so
that duration is reachable. An announcement past the header's ceiling is therefore dropped rather
than clamped, since clamping would announce something *shorter* than the core enforces and hand
the race to tonic, which is the one outcome the margin exists to prevent.

**What the brain does with it, measured end to end rather than assumed.** The entry that asked for
this supposed a brain that keeps working on an abandoned call: the store query, the memory cascade
and the reply serialization all burning for a reply nobody will read. A throwaway probe put a real
`grpc.aio` `BrainService` on loopback, whose `ListSessions` sleeps for twenty seconds, and drove it
from a real `BrainSeamClient` announcing an 800 ms plan. Both ends reported:

```
PROBE elapsed=801.000257ms error=Timeout { after: 800ms } announced=Some(1.05s)
{"time_remaining": 1.0484976768493652, "cancelled_after": 0.8001443940156605}
```

Three things are in those two lines. The header crosses to grpc-python intact and arrives as a
real deadline, so the brain can already see the bound rather than infer it. The body's own clock
won by the margin it was built to win by, the failure arriving as `Timeout` (terminal) at 801 ms
rather than as tonic's retryable `Connection` at 1.05 s. And the handler was cancelled at exactly
the moment the body dropped the call, 250 ms before the deadline it had been told, which is the
correction worth keeping: `grpc.aio` turns the client's stream reset into an `asyncio` cancellation
of the servicer coroutine, so the abandoned-work waste this entry was opened over was already
mostly cut before the header existed. What the announcement adds is therefore narrower than the
entry claimed and still real. It is a bound the brain holds on **its own** clock rather than one
that depends on a reset arriving, which a killed body, a half-open connection, or anything between
them may never send; and it is a number a handler can plan against before it starts work rather
than a signal it receives after. No legitimate call is at risk from that enforcement, since the
announcement is always longer than the bound the body has already given up at, and a turn
announces nothing.

**What is not in this slice.** The brain reading `time_remaining()` and shaping work with it,
which is where the second half of the value is: declining a cascade it cannot finish, logging the
abandonment as such, passing the remaining time down into the model host and the MCP tools it
calls. That is a decision per handler about what "not enough time left" means, in a different
tree with its own tests, and it is filed as
[R-322](../refinements/tasks/322-brain-reads-the-remaining-time.md) rather than carried here.

## Abandonment addendum (2026-08-20): the brain says a call was dropped, and prints what it had left

The courtesy header put a real deadline on the wire and the entry it left behind listed four
things a handler could do with the time it can now read. Three of them are a policy per RPC about
what "not enough time left" means: a listing that answers `DEADLINE_EXCEEDED` rather than spending
a store round trip nobody will read, a session read that returns the transcript without the memory
cascade it cannot fit, and the remaining time travelling onward into the model host and the MCP
tools where the seconds actually go. Each of those is a decision about one RPC or one downstream
port, and each changes what a caller gets back.

The fourth changes nothing a caller sees and needs no per-RPC judgement at all, which is why it is
the one that lands here: **a handler that was cancelled says so.**

### What the silence cost

`grpc.aio` turns the client's stream reset into an `asyncio` cancellation of the servicer
coroutine, measured at 800 ms against an announced 1.05 s in the addendum above. That cancellation
unwinds the handler's own `finally` blocks and then disappears. Nothing is logged, by grpc or by
this repo, so a call the body dropped is indistinguishable from a call that was never made: an
operator watching a slow brain sees the body's timeouts in one process and nothing at all in the
other. The work is already being cut, correctly and by the transport; what was missing is any
record that it happened.

### Decision 1: one interceptor, for the reason the token check is one

A `try` block per RPC body would be ten of them today and eleven the next time a method lands, and
the eleventh would be added by remembering. `AbandonedCallInterceptor`
(`brain/packages/orchestrator/src/cortex_orchestrator/abandon.py`) wraps each unary-unary behavior
in an arm that logs on `asyncio.CancelledError` and re-raises, exactly the structural argument
`auth.py` was built on. It is registered by `create_server` unconditionally, unlike the token
interceptor beside it: there is no posture to configure, only a line that is written or lost. It
goes **second**, so an unauthenticated call is refused rather than watched, work never started
being different from work abandoned.

The cancellation is re-raised on every path. A cancelled coroutine that swallows its cancellation
is a task that outlives its request, and this arm exists to make an abandonment visible, never to
change what it does.

### Decision 2: the reading is printed, and nothing branches on it

The line carries the RPC's wire `method` and `context.time_remaining()`, and interprets neither.
The reading answers three different facts and an operator can tell them apart by the number:

| Reading | What ended the call |
| --- | --- |
| `0`, or a sliver of the window | the announced deadline expired; grpc floors the reading at zero rather than letting it run negative, and a loaded machine can deliver the cancellation with microseconds of the window still unspent (the later addendum below measured that) |
| a value well above zero | the caller stopped waiting early, which is the shipped body on **every** call, since it enforces a bound strictly shorter than the one it announces (the grace margin above) |
| `None` | the caller announced no deadline at all, so what arrived was a disconnect |

A branch here would be the per-RPC policy this addendum is deliberately not landing, wearing the
formatter's hat. The floor at zero is worth writing down because it is the difference between the
line an operator reads and the line the design predicted: the addendum above expected a negative
remainder and the measurement on an unloaded machine returns exactly `0`, as an `int`. Under load
it returns the sliver instead, which the later addendum below measures and which is why the suite
bounds this reading rather than pinning it.

### Decision 3: the fence is the method's shape, not a list of names

`Converse` announces no deadline and must keep announcing none: a turn is long by design, and a
stream reporting an abandonment against a deadline would be the first half of enforcing a bound
this seam deliberately does not have. It is also the service's only streaming method, so a handler
carrying no unary-unary behavior is passed through untouched, and that single condition *is* the
fence. The alternative, ten method names in a set, would be a list somebody has to keep current
and would fence nothing on the day it went stale.

An unserviced method (the continuation resolving to `None`) is passed through for the same reason
the token interceptor passes it through: there is nothing there to watch.

### Distrust green

Five mutations, each applied to `abandon.py` alone with the orchestrator suite re-run, then
restored:

| Mutation | Reddens |
| --- | --- |
| the `except` arm deleted, so a cancelled handler prints nothing | 4 |
| the cancellation swallowed instead of re-raised | 3 |
| every handler watched, not only the unary-unary ones | the stream passthrough, and then **hangs** the wire `Converse` suite, a stream rebuilt as a unary handler having no behavior at all |
| the `method` field dropped | 4 |
| the `time_remaining` field dropped | 4 |

The third row is the fence proving itself: the shape check is not a tidy way of skipping one
method, it is the only thing keeping `Converse` a stream.

### Verified over the wire

The end-to-end case is not a fake context. A real loopback `grpc.aio` `BrainService` built by
`create_server`, whose `ListSessions` never answers, is driven by a real stub announcing a 200 ms
deadline; the client is told `DEADLINE_EXCEEDED`, the server cancels the handler, and the line
arrives naming the RPC's own wire path with a `time_remaining` that has run down to nothing worth
spending. That case is what proves the interceptor is installed at all, which no unit test of the
wrap can say.

### Consequences

- A slow brain is now visible from the brain's own logs, not only from the body's. The abandoned
  call names which RPC was dropped and how much of the announced window was left when it was.
- The level is `WARNING` rather than `INFO`: an abandoned call is work spent on a reply nobody
  read, and on a healthy deployment it should be rare. If it turns out to be routine on this
  machine, that is a fact about the timeouts worth being told loudly.
- `docs/modules/brain-orchestrator.md` gains the interceptor beside the token one.

### Deferred by this addendum

The three shapes that are a policy per RPC or per downstream port, carried forward together
because they share the question this one did not have to answer:
[R-341](../refinements/tasks/341-nothing-declines-work-it-cannot-finish.md).

## Addendum (2026-08-20, later): the clamp the abandonment test describes is not the one it asserts

A close-out review of the addendum above found its expiry case explaining itself with a fact it does
not check. The test says grpc clamps the remaining time at zero rather than letting it go negative,
"so it lands there", and then asserts that the reading is below half the announced window, which
every reading in that half satisfies. The commit that landed it made the stronger claim in its body,
that the reading arrives as an integer zero, and nothing in the suite holds that.

The loose bound may still be the right assertion. The reading is a real clock, so a case demanding
exactly zero fails on a scheduler hiccup rather than on a regression, and that is an honest argument
the file does not make; what it makes instead is an argument for a stricter assertion than it
carries. Either the prose comes down to what the bound checks, or the clamp is asserted beside it.
Filed as [R-346](../refinements/tasks/346-a-clamped-reading-nothing-pins.md).

## Addendum (2026-08-21): the clamp is asserted, and the reading is spelled out rather than echoed

**Two of this addendum's assertions came back out the same day, and the last addendum below is why:
`remaining == 0` and the literal `time_remaining=0` tail both hold on an idle machine and both fail
under load.** What survives is the floor, `remaining >= 0`, and the half-window bound beside it.
The rest of this section stands as the record of what was measured and decided at the time, and its
120 readings are all still true of the machine that produced them; read it with the correction
below, which measured the same scenario with the machine saturated.

The addendum above left its expiry case explaining itself with a fact it did not check, and the one
below it filed that. This closes it by asserting the fact, which is the close that entry preferred
and made conditional on the clamp being real. It is.

### Re-derived from the tree first, and the entry's claim held exactly

`test_an_abandoned_unary_call_says_so_and_prints_the_time_it_had_left` still said that grpc clamps
the reading at zero rather than letting it go negative, "so it lands there", and still asserted only
`remaining < _ANNOUNCED_S / 2`, which every reading in the lower half of the announced window
satisfies. Nothing else in the suite held the clamp either: the parameterized case that prints
`time_remaining=0` is handed that `0` by the file itself, so what it pins is the rendering of a
value nobody observed.

### Measured before anything was asserted

The scenario the wire case drives was run 120 times against a real loopback `grpc.aio` server, in
two batches of 20 and 100, the second with all four trees of `just check` running beside it so the
machine was loaded rather than idle. Every one of the 120 readings was exactly `0`, and every one
was an `int` rather than a float, which is `max(deadline - now, 0)` answering with its own second
argument because the subtraction was already negative. That is the same result the abandonment
addendum recorded when it landed, now taken deliberately and at a size that can carry an assertion.

The clamp is also grpc's own stated contract rather than an accident of this machine: the
`ServicerContext.time_remaining` it inherits documents its answer as "a nonnegative float".

### Decision 1: three assertions, one per claim the prose makes

The case now asserts that the reading is not negative, that the announced window really has run
down, and that it lands on the floor:

| Assertion | What it is worth |
| --- | --- |
| `remaining >= 0` | the clamp itself, and the one that can never fail on a slow machine |
| `remaining < _ANNOUNCED_S / 2` | the window ran down, rather than the call ending some other way |
| `remaining == 0` | the landing the prose claims, measured 120 times before being demanded |

The half-window bound is kept although the equality implies it, and deliberately: it is the loose
half of the pair, so a reader who ever does see a scheduler hiccup redden the equality can see what
the case is really about without re-deriving it, and relax to the pair above rather than to nothing.

### Decision 2: the rendered tail spells the number out

The case's last assertion read `time_remaining={remaining}`, interpolating the value it had just
read into the string it checked the line against. An assertion that prints back whatever it read
cannot say what a real expiry renders as, and the rendering is the half of the original claim the
commit body actually made: an **integer** zero. It is now a literal `time_remaining=0`, which a
`0.0` fails. The method stays interpolated, because it carries its own assertion two lines up and
because the proto's package name is spelled in the proto and nowhere else.

### Distrust green

Three mutations, each applied to `brain/packages/orchestrator/src/cortex_orchestrator/abandon.py`
alone, replacing `context.time_remaining()` in the `extra` of the abandonment line with a constant,
each run over `packages/orchestrator/tests/test_abandon.py`, then reverted and the file diffed
against its pre-mutation copy:

| Mutation | Reddens | The wire case fails on | Before this change |
| --- | --- | --- | --- |
| `0.05`, a grpc that stopped clamping and reports the sliver | 4 | `remaining == 0` | **green** |
| `-0.05`, one that reports the negative remainder instead | 4 | `remaining >= 0` | **green** |
| `0.0`, one that clamps to a float | 4 | the rendered tail | **green** |

The last column is the point. Each mutation was also run against the case exactly as it stood
before this addendum, and all three passed it: `0.05` and `0.0` are both below half the announced
window, and `-0.05` is below it too. The three that redden besides the wire case are the
parameterized renderings, which redden on any constant because a constant is what they vary.

### Consequences

- The suite now holds every sentence the file, `abandon.py`'s module docstring and
  `docs/modules/brain-orchestrator.md` say about the expiry reading. None of them is a claim a
  reader has to take on trust any more.
- A grpc release that changed this behaviour fails here loudly, naming which of the three claims
  moved, rather than passing under a bound that never described it.

### What this opens

The wire case is the only place the reading is real, and it exercises one of the three facts the
line distinguishes. The other two, a caller that stopped early and a caller that announced no
deadline, are only ever values this file hands the wrap, so the table in the abandonment addendum
above is pinned in one row of three. Filed as
[R-351](../refinements/tasks/351-two-readings-only-a-fake-ever-produced.md).

## Addendum (2026-08-21): what the announced deadline is worth downstream, decided elsewhere

The abandonment addendum above left three shapes, each a policy about one RPC or one downstream
port, and all three are now decided. None of them landed here, and the reason is one finding that
belongs on this record rather than on the one that carries the work.

**No unary handler on this seam reaches a model host or a tool sidecar.** The ten of them read the
session store, the schedule store, the preference store, the residency report and, for a delete's
cascade, the memory store. Every model-host
call and every tool call in this brain is made from a `Converse` turn, from boot recovery, or from
a background loop, and `Converse` announces no deadline at all. So "the remaining time travels"
had no route to travel by: the deadline a downstream call could inherit does not exist, and
building the plumbing to inherit it would be the first half of enforcing on `Converse` the bound
this seam deliberately does not have. The fence held by being looked at.

What that shape reduced to, once the announced deadline was out of it, is that a downstream call
should have a bound at all. One of the two already did: every `ModelHost` verb spends
`CORTEX_MODELHOST_TIMEOUT_S`, which is also compared at boot against the worst stop the host
reports. The tool seam had none, in the strong sense that the MCP session's own wait for a response
is `anyio.fail_after(None)`. That is where the work went, and it is recorded in the ADR-0009 bound
addendum rather than here, because it is a property of the tool client and not of this transport.

The two per-RPC shapes were declined on their merits and kept their own files: an early
`DEADLINE_EXCEEDED` from `ListSessions` turns on a floor nobody has measured and would have the
brain answering a deadline that has not expired
([R-360](../refinements/tasks/360-a-read-that-will-not-fit-declines-early.md)), and the partial
session read describes a memory cascade no read path on this seam has
([R-361](../refinements/tasks/361-a-read-rpc-recalls-nothing-to-omit.md)).

## Addendum (2026-08-21, later): the expiry reading is a clock, so the case bounds it

The addendum two above asserted `remaining == 0` on the wire case, on 120 readings that were all
exactly `0` and all `int`. Hours later the same case reddened inside a mutation sweep over the
whole brain suite, on an arm that changed a comparison no part of this path reaches. That was
filed as a suspected load-sensitive flake rather than diagnosed, and this addendum is the
diagnosis: it is one, it is easy to reproduce deliberately, and the exact assertion is what comes
out.

### Measured under load, on the same scenario, four ways

The load was 48 busy shell loops on a 24 core machine, twice oversubscribed, with a second full
`pytest` run of the brain suite beside them, which is the shape of the run that first reddened it.

| Run | What was driven | Result |
| --- | --- | --- |
| idle baseline | 20 replays of the wire scenario | 20 readings of `0`, every one an `int` |
| under load | 200 replays of the wire scenario | 32 positive floats, 168 integer zeros |
| under load | 30 runs of the case itself, one `pytest` process each | 5 reddened, all on `remaining == 0` |
| under load | one full brain suite of 2831 cases | this case reddened, alone, on `remaining == 0` |

The positive readings ran from 0.000017 s to 0.0073 s, median 0.0018 s. The largest is under 4% of
the announced 0.2 s window and a thirteenth of the half-window bound that was standing beside the
equality the whole time. The last row is the original observation reproduced with no mutation in
the tree at all, which is what settles the question the flake was filed with.

`max(deadline - now, 0)` answers with its own second argument, an `int`, only when the subtraction
has already gone negative, which needs the cancellation to reach the handler after the deadline
passed. That is the normal ordering and it is not the guaranteed one: a loaded machine can run the
handler's cancellation while microseconds of the window are still unspent, and then the reading is
the sliver. grpc's own contract is the floor, "a nonnegative float", and the floor is all it is.

### Decision: assert the floor and the bound, and pin the rendering where it is deterministic

`remaining >= 0` stays, being the floor and grpc's stated contract. `remaining < _ANNOUNCED_S / 2`
stays and is now the whole of the second claim: the window really ran down, rather than the call
ending some other way with most of it left. `remaining == 0` comes out, and so does the rendered
tail beside it, which pinned the same reading in the same way and would have reddened on the same
runs had it been reached first.

The bound is kept at half the window rather than tightened to the measured maximum. A threshold
just above 0.0073 s would be this machine's worst case under one synthetic load promoted to a
suite-wide invariant, which is the flake again at a different number; half the window carries the
claim the case is actually making, and carries it with a thirteenfold margin over anything
measured.

What the rendering of an expiry looks like is still pinned, in the parameterized case that hands
the wrap a `0` of its own. That is the honest place for it: there the value is the same value
twice, so the assertion says what `0` prints as, where over the wire it could only print back
whatever the clock had said.

### Distrust green

Four constants replacing `context.time_remaining()` in the `extra` of the abandonment line in
`brain/packages/orchestrator/src/cortex_orchestrator/abandon.py`, each run over the whole
orchestrator suite (`packages/orchestrator/tests`, 450 cases, 19 of them deselected as
integration), then reverted and the file read back off disk:

| Mutation | Reddens | The wire case fails on |
| --- | --- | --- |
| `-0.05`, a grpc reporting the negative remainder | 4 | `remaining >= 0` |
| `0.15`, a reading that has not run down | 4 | `remaining < _ANNOUNCED_S / 2` |
| `0.05`, a grpc that stopped flooring and reports the sliver | 3 | nothing; a real expiry reads like this under load |
| `0.0`, one that floors to a float | 3 | nothing; the renderings carry it |

The bottom two rows are the price, stated rather than hidden. Both mutants still die, in the three
parameterized renderings, which redden on any constant because a constant is what they vary; what
they no longer die to is the wire case, because the wire case can no longer tell them from the
truth. The top two are new: nothing held the half-window bound to being able to fail before, and
the `0.15` row is that proof.

The corrected case was then re-run 40 times under the same load that reddened 5 of 30 before it,
and reddened none.

### What this opens

Two things, both narrower than the entry that closed here. The wire case can no longer distinguish
a grpc that floors the reading from one that reports the sliver, since a real expiry now produces
both: [R-371](../refinements/tasks/371-a-floor-and-a-sliver-are-indistinguishable.md). And the
half-window bound's margin is a judgement over one machine under one synthetic load, with nothing
sampling how wide the sliver grows on a busier one:
[R-372](../refinements/tasks/372-the-sliver-is-unsampled-over-time.md).

## Addendum (2026-08-22): all three readings come off the wire, and the floor stops being a race

Three entries were open on one reading. Two of the three facts the abandonment line distinguishes
were only ever values the test file handed the wrap
([R-351](../refinements/tasks/351-two-readings-only-a-fake-ever-produced.md)); the wire case that
does produce a real reading can no longer tell a grpc that floors it from one that reports the
unspent sliver
([R-371](../refinements/tasks/371-a-floor-and-a-sliver-are-indistinguishable.md)); and the margin
under the half-window bound was measured once and is sampled by nothing
([R-372](../refinements/tasks/372-the-sliver-is-unsampled-over-time.md)). They are one question,
so they are answered together: **each of the three readings gets the wire case of the shape that
produces it in production**, and the third entry is declined because the first two take away the
only thing it was protecting.

### Re-derived first, and one recorded claim did not hold

Every claim in the three entries was checked against the tree before anything was written. The
wire case did assert exactly `remaining >= 0` and `remaining < _ANNOUNCED_S / 2`; the other two
rows were driven through `_Context`; the bound was 0.1 s against 0.2 s announced. The one claim
that did not hold is R-371's count: it says the `0.05` mutation "reddens three cases, and all
three are the parameterized renderings". Re-run here before any change, that mutation reddens
three, and the addendum above records the same three, so the entry is right about the tree and
wrong about nothing. What did not survive is a claim of R-351's, that the `None` row is a shape
"the body never sends, so it may be honest to leave that row as a rendering test". The row is not
about what the body sends. It is about what grpc answers for a call with no deadline, and a grpc
that folded that case into a `0` would turn an operator's three way reading into a two way one
with every test still green. That reasoning is why the row got a wire case rather than a written
excuse.

### The shape each reading really has in production

The reading is not three arbitrary numbers. Each one is a different thing going wrong on this
seam, and once they are named that way, each has an obvious scenario:

| Reading | How it happens on a deployed brain | Wire case |
| --- | --- | --- |
| a value well above zero | the shipped body on **every** call: it announces a deadline and enforces a bound strictly shorter, so it drops the call with most of the announcement unspent (the grace margin addendum above) | announce wide, wait until the handler is really entered, cancel |
| an integer `0` | the body was killed or the connection half opened, so the cancellation it would have sent never arrives and the announced deadline is enforced by the only clock left, which is the brain's own | announce in `grpc-timeout` metadata with no `timeout=` beside it |
| `None` | anything reaching this seam without announcing a deadline, then disconnecting | no deadline, wait until the handler is entered, cancel |

The case that was already there, a client whose own `timeout=` fires on the same announcement it
sent, is the fourth and is kept: it is the only one where two clocks race, and it is where the
floor is exercised under the one condition that could make the reading negative. It is also, read
against the table, the *least* faithful of the four, because the grace margin exists precisely so
that the shipped body never arms its own clock on the deadline it announced.

### Decision 1: the ordering is a fact, never a wait

A cancellation that arrives before the handler is entered produces no line at all, so the two
cases that cancel have to cancel after it. The never answering store now sets an `asyncio.Event`
from inside the handler and the fixture hands it out beside the target, so "the handler is
running" is something the case knows rather than something it hopes. The line itself is waited for
on the existing latch. No case sleeps to order two events, and the one case that wants the
deadline to have passed does not wait for that either: announcing through the header with no
client timer means no clock exists that could fire early, so the subtraction behind the reading
has always already gone negative by the time anything reads it.

That last point is the whole of decision 2, so it is worth stating as mechanism. `grpc-timeout` is
how a deadline crosses the wire and the body sends it. Passing it as metadata and omitting
`timeout=` announces to the server and arms nothing here, which is exactly the deployed shape
where the body is gone. The server's deadline can only be enforced once it is due, so
`max(deadline - now, 0)` answers with its own second argument, an `int`, every time.

### Decision 2: the floor is pinned where the sliver cannot exist

This is the answer to R-371, and it is neither of the two shapes that entry weighed.

Not "drive the scenario N times and assert at least one reading is the integer floor". That buys a
real distinction with N loopback round trips at the announced window each, and it buys it
probabilistically: the reddening it prevents is the one where every one of N happens to be a
sliver, which is a flake at a lower rate rather than no flake. Under the load measured below, 51
of 400 replays were slivers, so a run of N slivers is not impossible at any N a suite can afford.

Not "let the deadline pass by a wide margin before the cancellation is delivered" either, and R-371
names its own obstacle correctly: nothing in a case chooses when grpc delivers a cancellation.
Withholding the event loop with a busy wait does force it, and was tried and works, but it costs
real suite time to guarantee an ordering that the header shape gets for free by removing the
second clock instead of outrunning it.

The case therefore asserts `isinstance(remaining, int)` and `remaining == 0`, and the rendered
tail `time_remaining=0` beside them. The `int` is the load bearing one: a reading still counting
down is a float whatever its value, so the type alone separates the floor from the sliver, and it
does so on a reading grpc produced rather than on one the file typed.

### Decision 3: the margin is declined, because it no longer protects anything

R-372 offered three shapes and said the third might be the answer. It is.

Not `just shuffle`, and not a periodic reading in the turn cost measurement's shape. Both would
sample a number, and the argument for sampling it was that a growing sliver would eventually
redden the half-window bound, whose only remaining value was the floor-versus-sliver distinction
R-371 filed. That distinction is now held by a case where the sliver cannot occur at all, so a
sliver that grew costs exactly one thing: the two-clock case reddening if it ever reached 0.1 s.

And the sliver cannot quietly reach 0.1 s, for a structural reason that the measurement below
turned up. A sliver is the gap between the client's clock firing and the server's window still
having something left, so it is bounded by the difference between the two, which is a function of
the call setup this scenario has to complete anyway. A sliver approaching half the announced
window would mean call setup taking half the announced window, and then the handler is not entered
before the deadline, no line is written at all, and the case reddens on the latch timing out,
which is a louder failure naming a real problem. Watching a number whose own upper bound is
already enforced by the case's precondition is watching for nothing.

What is deliberately not claimed: that the margin cannot narrow. It did, between the measurement
that chose the bound and this one.

### Measured under load before anything was asserted

The load was 48 busy shell loops on a 24 core machine, twice oversubscribed, with a full `pytest`
run of the brain suite running beside them, restarted in a loop so it was never absent. Load
average sat between 45 and 49 throughout. Each scenario was replayed 200 times against a real
loopback `grpc.aio` `BrainService` built by `create_server`.

| Scenario | Readings | Spread |
| --- | --- | --- |
| both clocks armed (the older case) | 178 integer `0`, 22 positive floats | slivers 0.00037 s to 0.0107 s, median 0.0036 s |
| the brain's clock alone (header only) | 200 integer `0`, no floats | no sliver at any replay |
| the caller stops early | 200 floats, no integers | 9.9789 s to 10.0993 s against 10 s announced |
| no deadline announced | 200 `None` | not applicable |

An earlier 200 replay run the same hour, under the busy loops alone, read 171 integer `0` and 29
slivers, widest 0.0076 s. Across both saturated runs that is 400 replays of the two clock
scenario, 349 integer `0` and 51 slivers, **widest 0.0107 s**. The previous measurement's widest
was 0.0073 s, so the margin under the 0.1 s bound went from thirteenfold to nine and a halffold
between two comparable loads. The bound is unchanged, both because nine and a halffold is still a
wide margin and because tightening it toward whatever this machine last produced is the mistake
that addendum already declined once.

**A reading above the announced window was really observed.** 41 of the 200 caller stops early
replays read *higher* than the 10 s the client announced, the widest 10.0993 s. This is not a
clock going backwards: the server's window is the one the header encoded, and what the header
encoded is not what this client asked for. grpc-python rounds a timeout **up** onto a coarse unit
ladder, so a `timeout=10.0` reaches the server as `10100ms`; the encoding addendum below reads the
ladder off the wire. A separate probe on a bare `grpc.aio` server read the server side window at
handler entry as 0.200092 s for an announced 0.2 s, 1.05897 s for 1.05 s, and 3.008877 s for
3.0 s, all above the announcement. The new case therefore asserts a lower bound only. An upper
bound at the
announcement would read as obviously safe and would be asserting something grpc does not promise,
which is the exact defect these three entries exist to correct.

### Distrust green

Nine mutations, each applied to
`brain/packages/orchestrator/src/cortex_orchestrator/abandon.py` alone and each run over the
**whole orchestrator suite** (`packages/orchestrator/tests`, 448 selected, 19 deselected as
integration), then reverted and the file compared against its pre-mutation text:

| Mutation | Reddens | Was, before this change |
| --- | --- | --- |
| the `except` arm deleted | 7 | 4 |
| the cancellation swallowed instead of re-raised | 3 | 3 |
| every handler watched, not only the unary-unary ones | the stream passthrough, and then **hangs** `test_converse_grpc.py`, confirmed at 150 s with no completion | same |
| the `method` field dropped | 7 | 4 |
| the `time_remaining` field dropped | 7 | 4 |
| `-0.05`, a grpc reporting the negative remainder | 7 | 4 |
| `0.15`, a reading that has not run down | 7 | 4 |
| `0.05`, a grpc that stopped flooring and reports the sliver | **6** | 3, all renderings |
| `0.0`, one that floors to a float | **6** | 3, all renderings |

The last two rows are what R-371 asked for and the only ones that needed a new kind of evidence.
Both used to die only in the parameterized renderings, which redden on any constant because a
constant is what they vary, and the addendum above recorded that as the price of the bound. Both
now die in the floor case as well, and the assertion each fails is `isinstance(remaining, int)`,
checked directly: `isinstance(0.05, int)` and `isinstance(0.0, int)`. That is a reading grpc
produced, in a scenario where a real expiry cannot look like either constant, which is precisely
what a rendering test cannot supply.

The swallow row is worth its own sentence, because its count did not move and the reason is not
that the new cases are weak. A client that has already been told its deadline expired, or that
cancelled the call itself, is told the same thing whether or not the servicer re-raises, so the
three renderings remain the only cases in a position to watch the cancellation arrive.

The full suite was then run 40 times, one `pytest` process each, under the same load. None
reddened.

### Consequences

- Every row of the reading table in the abandonment addendum above is now observed over the wire,
  in the shape that produces it in production, rather than pinned on a value the test file chose.
- `docs/modules/brain-orchestrator.md` and `abandon.py`'s module docstring say what the suite
  holds and no more, including the two things that are now known and were not: the reading's type
  is what separates the floor from the sliver, and the reading is not bounded by the client's
  announcement.
- The suite gains three loopback cases. Two are effectively instant, since they cancel as soon as
  the handler is entered; the header only case costs the announced 0.2 s, the same as the case
  that was already there.

### What this opens

One, narrower than any of the three closed here. The grace margin addendum above sizes its 250 ms
partly on "the header encoding's truncation to whole units, at most a millisecond and exactly zero
for every value the shipped plan produces". The probe above measured the server side window
running about 100 ms above a 10 s announcement and about 9 ms above a 1.05 s one, which is two
orders of magnitude past that sentence. The direction is the safe one, the brain waiting longer
than announced rather than shorter, so no bound is at risk; the sentence is still wrong and the
shipped plan's own announced values were never measured.
[R-381](../refinements/tasks/381-the-header-encoding-error-is-larger-than-recorded.md).

## Addendum (2026-08-24): the turn's silence is bounded, where its length still is not

Every unary call on this seam has been bounded since the deadline addendum above, and the eager
`converse` dial with them. The turn's own stream was left out on purpose, and the exemption above
says why: a turn is long by design, so a clock on its *length* would end legitimate work. That
argument is sound about a working turn and silent about a stalled one, which is the gap this
addendum closes.

### Re-derived from the tree first, and one of the entry's guesses did not hold

The deferral this closes was written on 2026-08-18 and **90 commits have landed since**, eight of
them under `body/` and two of those inside this decision's own area: the courtesy `grpc-timeout`
header, and the correction to what tonic's own expiry classifies as. So the entry was read as a
proposal and every claim in it was checked against today's code rather than taken on trust:

- `RetryPlan::deadline_for` still answers `None` for `Converse` alone
  (`body/crates/core/src/retry/plan.rs`), and `announced_deadline_for` therefore announces nothing
  for a turn, which `body/crates/rpc/tests/client.rs` pins over the wire.
- `RetryingTransport::converse` was a pure pass-through, and the shell's turn path did not even
  reach it: `body/app/src-tauri/src/converse.rs` dialed a `BrainSeamClient` eagerly and called
  `converse` on the client itself.
- The harm is exactly as described, and the overlay is where it is visible. A reply leaves its
  streaming state on a terminal event or on a transport error and on nothing else
  (`applyEvent` and `endTurn` in `body/app/src/overlay/turnState.ts`, the `transportError` arm in
  `overlayState.ts`), and the Tauri bridge only feeds that sink from a channel message, its
  `invoke(...).catch` firing on a rejection the command never produces
  (`body/app/src/bridge/tauriBridge.ts`). So a brain that accepts the turn and then stops sending
  leaves the thinking indicator up for as long as the process lives.
- The recovery the entry counted on is real: the Stop control ends the turn in place, keeping the
  partial text and setting no error (`stop` in `overlayState.ts`). That is why this was recorded as
  recoverable rather than terminal, and why it waited.

One claim in the entry did **not** survive, and it is the interesting one. The entry guessed that
the silence before a first token would be the longer of the two numbers, a deep model on a cold
cache being quiet for a while. On this deployment the reverse is true by an order of magnitude, for
a reason that has nothing to do with inference. See the derivation below.

### The instrument is the gap between events, not a deadline

`retry::gap::within_gaps` wraps the turn's stream and bounds **the silence between its items**.
Every delta, tool activity, tool outcome, status, confirm request and confirm resolution resets the
clock, so a turn may run for an hour as long as it keeps arriving, and only quiet is spent. Nothing
new is asked of the `Sleeper` port: one poll of the stream is a future, and `bounded` already runs
a future against a duration and reports which won, so the gap decorator composes what the deadline
path composes.

`RetryPlan::gaps_for(method)` is the door, and it is the mirror of `deadline_for`: `Some` for
`Converse` alone where the other is `Some` for everything else. Together they carry an invariant
worth more than either half, asserted over every variant in `retry_plan.rs` rather than left in
prose: **every call on the port is bounded, by a clock on the call or a clock on its silence, and
never by both**.

The turn still announces nothing on the wire. A gap is not a deadline the brain could act on, and
`grpc-timeout` cannot express one, so `announced_deadline_for` is untouched and the sentence in
`brain/packages/core/src/cortex_core/tool_deadline.py` about a turn announcing no deadline stays
true.

### Deriving the first-event gap: 600000 ms

What can legitimately pass before a turn's first event is a chain of brain-side waits, and the
brain bounds each of them itself. Taking those bounds rather than guessing at a first token:

| Bound before the first event | Value | Declared in |
| --- | --- | --- |
| the swap's wait for the subagent pool to quiesce | 60 s | `cortex_core/model_host.py`, `DEFAULT_SWAP_DRAIN_TIMEOUT_S` |
| the swap's wait for the model to report ready | 300 s | `cortex_core/model_host.py`, `DEFAULT_SWAP_LOAD_TIMEOUT_S` |
| the wait on the first token, per stall ceiling | 120 s | `cortex_orchestrator/config.py`, `stall_timeout_s` |

480 s of waiting that the brain itself ends with a reported failure, and the shipped gap is 600 s,
the remainder being margin for the stretches no brain-side budget covers: recall, prefill, and a
first round the brain streams nothing visible for.

The measurement says the same thing with a lot of room to spare. The deep tier loads in **99.6 s**
against the cortex pick's 38 to 52 s ([ADR-0004](ADR-0004-model-lineup.md) lineup table), and the
worst time to first token measured on this card is **17.5 s** on a contended cortex, derived at
**45.5 s** for the deep tier by the load ratio (the stall-ceiling addendum of
[ADR-0005](ADR-0005-llamacpp-engine.md), measuring
[docs/runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md)). A screen capture adds 0.6 s
([ADR-0029](ADR-0029-vision-screen-capture.md)), so vision is noise at this scale. The slowest
first event anyone here has timed is therefore about 145 s, and the shipped gap is roughly four
times it.

### Deriving the idle gap: 7200000 ms, and why it is the longer one

The long silences on this deployment can only happen once a turn is under way, and the longest of
them is a delegated subtask. `spawn_subagents` emits one `StatusUpdate` naming the batch and then
waits (`cortex_core/spawn.py`), and while a subagent runs the only thing that reaches the seam is
an audited tool step of its own (`cortex_core/subagent_attempt.py`). A subtask that writes prose
and calls nothing is therefore **silent at the seam for its whole run**, and its run is bounded by
two numbers the brain ships:

| Bound on one delegated subtask | Value | Declared in |
| --- | --- | --- |
| the wait for the CPU budget to admit it | 3600 s | `cortex_core/scheduler.py`, `DEFAULT_ADMISSION_WAIT_S` |
| the run once admitted | 2400 s | `cortex_core/subagents.py`, `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` |

6000 s of legitimate silence, and the shipped gap is 7200 s, a fifth of it as margin. That is a
long time to hold an indicator, and it is the honest number rather than a comfortable one: a bound
under it would turn a slow success into a failure, which is the argument the admission wait's own
declaration makes about itself ("worse than the unbounded wait it replaces"). What this removes is
"forever", not "slow", the same sentence the resident tier's stall ceiling was sized by.

**The obvious tightening is refused, and the reason is not caution.** The delegation announces
itself, so the body could widen the gap only on seeing that status and hold every other turn to
something tight. Progress rides a best-effort sink that **drops an event on a saturated buffer** by
design (`cortex_core/progress.py`), so the announcement may never arrive, and a decision that ends
a turn must not rest on having received one. The change that would let this number come down is a
heartbeat the brain owes on a long silent stretch, filed below.

Neither number is a measurement of a stall, because nobody here has observed one: the trigger this
entry carried never fired. They are argued from budgets the repo ships and measurements it holds,
and the mechanism is what is being landed. A deployment that runs without the delegating sidecars
can turn the idle gap down to the first-event figure, and
[docs/runbooks/body-overlay.md](../runbooks/body-overlay.md) says so.

### What the body does when a gap fires, and why it is an error

The stream yields one final `Err(TransportError::Timeout { after })` carrying the gap that expired
and then ends, dropping the inner stream, which for the gRPC adapter resets the turn so a stall
nobody is waiting for stops costing the brain.

The alternative was to end the stream silently, which would read as the cancel the user could have
performed themselves, and it is **not available**: the overlay leaves a reply streaming until a
terminal event or an error reaches it, so a stream that merely stopped would leave the indicator
exactly where the stall did. Delivering the timeout is also the truer of the two. The user's own
Stop is a decision they made and records no error; a gap that expires is evidence the brain stopped
serving, and the overlay already has the surface for it: `linkFailed` draws a `timeout` `down`
rather than `degraded`, because degraded means the brain answered and an expired gap is precisely
the absence of an answer (`body/app/src/overlay/linkState.ts`). The reply settles on the words that
did arrive, carrying why it stopped, and the dot goes red. No overlay change was needed for any of
it, the `timeout` kind having landed with the per-attempt deadline.

### Where it is applied

`RetryingTransport::converse`, so the port's decorator bounds every method it wraps, and the
shell's turn path was rewired to run through that decorator rather than calling the dialed client
directly (`body/app/src-tauri/src/converse.rs`). The decorator still refuses to retry a turn, so
wrapping buys exactly one thing there. One `RetryPlan` is read for both halves of that command, the
dial's deadline and the stream's gaps, the same "one plan, read once" shape `seam.rs` already uses.

### Distrust green

Twelve mutations, each applied to `body/crates/core/src/retry/gap.rs` alone and each run over the
**whole `body-core` suite** (`body/crates/core`, 156 tests across ten binaries, 4 ignored as
integration), then reverted and the file compared against its pre-mutation text:

| Mutation | Reddens |
| --- | --- |
| the first-event gap raised to the idle one, making the two numbers one | 1 |
| the idle gap lowered to the first-event one, the same collapse the other way | 1 |
| every wait measured against the idle gap | 6 |
| every wait measured against the first-event gap | 4 |
| an arriving event no longer ends the first-event window | 4 |
| an expired gap ends the stream silently instead of reporting | 5 |
| an expired gap does not end the stream, so the wait repeats | **hangs**, 240 s with no completion |
| a stream that ended on its own reported as a stall | 4 |
| the plan answers no gaps for the turn | 4 |
| the plan answers gaps for every method | 1 |
| the absent bound spelled as zero rather than as forever | 1 |
| the caller's gaps ignored for the shipped ones | 5 |

The two rows that redden one test each are the ones that should: the constants have exactly one
reader, the test that pins them and their ordering.

**The first run of this table was wrong, and the reason is worth keeping.** It was run without
`--no-fail-fast`, so cargo stopped at the first test binary that failed and the counts were counts
of `retry.rs` alone: three rows read 1 where they redden 4 or 6, and the row that hangs read as a
**survivor**, because the binary that hangs is never reached when an earlier one fails. A mutation
count taken from a fail-fast run measures the alphabet, not the suite.

### Consequences

- A turn that stops arriving now ends, is reported, and settles the overlay's indicator, at the
  cost of the silence the two gaps allow. Nothing bounds a turn's length, and nothing here can:
  the bound is on quiet alone.
- `CORTEX_BRAIN_TURN_FIRST_GAP_MS` (default 600000) and `CORTEX_BRAIN_TURN_IDLE_GAP_MS` (default
  7200000) join the retry knobs in the shell, parsed by the same `env_millis`.
- `RetryPlan` gains a `turn_gaps` field. Every existing construction spreads `..Default::default()`
  and is unaffected.
- `body_core` gains `async-stream`, which the rpc adapter's own `converse` already uses. It is a
  generator ergonomics macro over `futures-core`, so the crate stays free of runtimes and I/O.
- A brain that legitimately goes quiet for longer than a gap now fails a turn where it used to hang
  it. On the shipped numbers that means a delegated batch past two hours, and the knob is the
  answer.

### What this opens

One, and it is the bound that would make the idle gap a useful number rather than a backstop.
Nothing crosses the seam while a turn waits on delegated work, so the body cannot tell a brain
thinking from a brain gone, and the only bound it can honestly draw is above the longest legitimate
silence. A heartbeat the brain owes on a long silent stretch, or a status the delegation refreshes
rather than emits once, would let the gap come down from hours to minutes and would say something
the overlay could show while it waits.
[R-421](../refinements/tasks/421-a-silent-turn-owes-the-body-a-heartbeat.md).

## Encoding addendum (2026-08-25): the header error is the other client's, and the margin stands

The grace margin addendum above sizes its 250 ms on three things and the middle one, "the header
encoding's truncation to whole units, at most a millisecond and exactly zero for every value the
shipped plan produces", was written by reading tonic's encoder rather than by measuring anything.
The abandonment measurement then read server side windows running about 9 ms above a 1.05 s
announcement and about 100 ms above a 10 s one, which is two orders past that sentence, and the
deferral this closes recorded the gap without naming its cause. Both halves are now measured: what
produces the excess, and what the shipped plan's own announcements actually do on this seam.

### Re-derived first, and the entry was wrong about the tree in the half that mattered

The entry says the shipped plan's announced values "were never among the three measured". They are
measured, over a real wire, and have been since the slice landed:
`an_announcing_client_tells_the_brain_each_call_s_own_deadline`
(`body/crates/rpc/tests/client.rs`) reads `grpc-timeout` back off the request a tonic fake brain
received, parses it as a duration rather than as a string, and asserts it equals
`announced_deadline_for` for a probe and for a read. That test is in the gated suite and green
here. What had never been measured is the other end of the same call: what a **grpc-python** brain
makes of those headers, which is the pairing that actually ships.

The entry is right that the mechanism was never traced, and right that the direction is safe.

### The mechanism: grpc-python's client rounds up, and the server's stamping only subtracts transit

A loopback `grpc.aio` `BrainService` was driven from grpc-python's own client with `timeout=`, with
the server run under `GRPC_TRACE=all` so its HPACK parser prints each header as received. The
header is not what the client asked for:

| `timeout=` | `grpc-timeout` as the server received it | excess |
| --- | --- | --- |
| 0.2 s | `201ms` | 1 ms |
| 0.25 s | `251ms` | 1 ms |
| 0.5 s | `501ms` | 1 ms |
| 1.05 s | `1060ms` | 10 ms |
| 3.0 s | `3010ms` | 10 ms |
| 5.25 s | `5260ms` | 10 ms |
| 10 s | `10100ms` | 100 ms |
| 30 s | `30100ms` | 100 ms |
| 99 s | `99100ms` | 100 ms |
| 120 s | `121000ms` | 1000 ms |

That is a unit ladder with a step of 1 ms below a second, 10 ms up to ten seconds, 100 ms up to a
hundred, and a second beyond, and grpc-python rounds **up** onto it. The excess is bounded by one
step and is not constant: a call whose deadline had already run down past the step boundary by
encode time lands exactly on the request instead, which is why the same 1.05 s announcement read
`1060ms` on an idle run and `1050ms` on a traced one, and why the 60 s warm up call, which pays for
the connection before its header is written, arrived as `60000ms` while a warm 30 s call arrived as
`30100ms`. The server's own contribution runs the other way: `context.time_remaining()` at handler
entry was consistently a fraction of a millisecond below the header, never above it. So the
readings the abandonment addendum recorded, 1.05897 s against 1.05 s and 10.0993 s against 10 s,
are the client's encoder rounding up minus the server's transit, and the server's receipt time
stamping never adds anything at all.

**None of this is tonic.** tonic truncates rather than rounds, and picks the most precise unit that
fits in eight digits (`duration_to_grpc_timeout`, `tonic-0.14.6/src/request.rs`): nanoseconds below
0.1 s, microseconds below 100 s, milliseconds below about 27.8 hours, whole seconds past that. So
the loss on the body's own announcements is under a microsecond for anything this seam plausibly
announces, and the two clients differ in direction as well as in size.

### The shipped plan's announced values, measured against a real grpc-python brain

A throwaway probe put the loopback `grpc.aio` server back up and dialed it with the repo's own
`BrainSeamClient` announcing `RetryPlan::default()`, so the numbers under test are the plan's, not
a probe's pick: `announced_deadline_for(Health)` is 500 ms and `announced_deadline_for` for a read
is 5.25 s. Twenty warm rounds of a probe and a read, idle box:

| Announced | Header the brain received | Window at handler entry | Readings above the announcement |
| --- | --- | --- | --- |
| 500 ms | `500ms` | 0.498910 s to 0.499821 s | 0 of 20 |
| 5.25 s | `5250ms` | 5.248842 s to 5.249842 s | 0 of 19 |

The encoding is exactly lossless for both, which is what the sentence claimed and what had not been
checked in the pairing that ships. The brain's window is 0.16 ms to 1.16 ms **shorter** than the
announcement, that difference being the loopback round trip plus the brain's header parse, and it
is never longer. The phenomenon the deferral was opened over does not occur on this seam in either
size or direction; it occurs when grpc-python is the client, which the body never is and which the
brain's own test suite always is.

### Decision: correct the sentence, keep the number

Two of the three sizing terms were wrong, and neither in a direction that moves 250 ms.

- The loopback round trip plus header parse was recorded as "tens of microseconds" and measures
  about a millisecond, taken at the brain's handler entry rather than argued from a socket.
- The encoding truncation was recorded as "at most a millisecond". On tonic's ladder it is under a
  microsecond below 100 s, and exactly zero for both shipped announcements, so the sentence was
  pessimistic in the range that matters and silent about the one range where it fails: past about
  27.8 hours the ladder steps to whole seconds, and three announcements in four would then arm
  tonic's clock **shorter** than the bound the core enforces.
- The scheduler stall is untouched and is still the term that sizes the margin. The widest racing
  sliver measured on this machine, under twice oversubscribed load, is 0.0107 s (the 2026-08-22
  addendum above), so a quarter second is about twenty three times the worst stall ever observed
  here.

So `ANNOUNCED_DEADLINE_GRACE_MS` stays 250 ms, now for measured reasons rather than read ones, and
the sentence in the grace margin addendum and in `plan.rs` says what was measured. The one regime
where the encoding really can outrun the margin needs an absurd knob to reach and is filed rather
than guarded, below.

### Distrust green

No gate and no assertion changed here, so there is no mutation table to record: the corrections are
prose, in the addendum above, in `ANNOUNCED_DEADLINE_GRACE_MS`'s own doc comment, in
`docs/modules/brain-orchestrator.md`, and in one comment in `test_abandon.py` that explained the
above-the-announcement reading by the server's stamping instead of by the client's encoder. The
claim the corrected sentence now makes about the shipped values is already guarded, by
`an_announcing_client_tells_the_brain_each_call_s_own_deadline`, which fails if either announcement
stops crossing the wire as the duration the plan computed.

### What this opens

One, and it is the range the measurement turned up rather than the one it was aimed at. tonic
spells an announcement in whole seconds once it passes about 27.8 hours, so an announcement whose
millisecond remainder exceeds the margin arms tonic's own clock short of the bound the core
enforces, handing the race to the timer this design exists to make lose. It takes
`CORTEX_BRAIN_CALL_DEADLINE_MS` near a hundred million to reach, and `MAX_ANNOUNCED_DEADLINE`
currently filters only what the header cannot spell at all, eleven thousand years out.
[R-436](../refinements/tasks/436-an-announcement-past-the-millisecond-ladder-loses-the-race.md).

## Unit-ladder addendum (2026-08-25): the announcement filter moves down to the rung that keeps order

The encoding addendum above closed by naming one regime it had not guarded: past about 27.8 hours
`grpc-timeout`'s unit ladder steps from milliseconds to whole seconds, and an announcement
truncated onto that step arms tonic's clock under the bound the core enforces. This is the
decision about that regime.

### What the tree actually does, re-derived

Four readings, each taken here rather than carried over.

- **The ladder.** `duration_to_grpc_timeout` (`tonic-0.14.6/src/request.rs`) walks nanoseconds,
  microseconds, milliseconds, seconds, minutes, hours, takes the first unit whose count is at most
  99,999,999, and **truncates** onto it. So the millisecond rung ends at 99,999,999 ms, which is
  99,999.999 s, and everything above it is spelled in whole seconds.
- **Announcing is arming.** `Request::set_timeout` writes the header and nothing else, and the
  channel's `GrpcTimeout` layer (`tonic/src/transport/service/grpc_timeout.rs`) parses the header
  back off the outgoing request and sleeps on what it decoded. The interceptor in
  `body/crates/rpc/src/call.rs` calls exactly that.
- **The arithmetic.** With `announced = enforced + 250 ms`, write `r` for the enforced bound's
  millisecond remainder. Above the rung the decoded value is `enforced - r` when `r` is 1 to 749,
  so it falls **below** the enforced bound for 749 of every 1000 values of `r`, by `r` ms, up to
  749 ms. For `r` of 750 to 999 it stays above but the margin shrinks to `1000 - r` ms, as little
  as 1 ms, which is three orders of magnitude under the stall the margin is sized for. Only `r` of
  0 keeps the full quarter second. So the entry's "three in four" and "up to 749 ms" both hold,
  and understate it: only one remainder in a thousand leaves the margin intact.
- **The consequence.** tonic's own expiry classifies `TransportError::Connection`
  (`body/crates/rpc/src/status.rs`, and `tonics_own_expired_timeout_classifies_as_a_retryable_connection_failure`
  asserts `is_transient` on a real one), so a tonic timer that won the race turns one abandoned
  call into three. That is the amplifier this whole margin exists to prevent, confirmed rather
  than assumed.

The regime is reachable, not merely conceivable: `plan_from_env` (`body/app/src-tauri/src/seam.rs`)
parses `CORTEX_BRAIN_CALL_DEADLINE_MS` as a `u64` of milliseconds with no ceiling, and `RetryPlan`'s
fields are public besides.

### Decision: `MAX_ANNOUNCED_DEADLINE_MS` is the millisecond rung, and past it we announce nothing

The filter now sits at 99,999,999 ms instead of at 99,999,999 hours. It stops being a guard
against tonic's panic and becomes what it was always doing badly: the bound below which the
header can carry an announcement without reordering the two clocks. The panic is still on the far
side of it, four rungs up.

Four alternatives were weighed and rejected.

- **Clamp the announcement onto the ladder.** Announcing something shorter than the enforced bound
  is the race run deliberately, which is the answer this ADR already refused when the header
  arrived.
- **Round the announcement up onto the ladder ourselves.** This preserves both the courtesy and
  the order, and it is the only alternative that is not simply worse. It loses on coupling: the
  ladder is private to tonic, the rungs above seconds are minutes and hours, and reimplementing an
  encoder that is free to move under a version bump buys a configuration nobody wants at the price
  of a silent breakage nobody would notice.
- **Cap `CORTEX_BRAIN_CALL_DEADLINE_MS` in the shell.** It would leave `RetryPlan`'s public fields
  open, and it would quietly change a bound the operator configured, where the drop changes only
  what the brain is told.
- **Decline as unreachable.** It is not unreachable. It is one env var away, with no ceiling on the
  parse, and "nobody would write that" is a statement about intent rather than about the system.

What the drop costs is one hint: the brain stops learning that a 27.8-hour call has been
abandoned. What it never costs is the call, which the core's own bound still ends, and that is the
rule this adapter already followed for an unspellable deadline.

The comparison is against whole milliseconds, so it also refuses the sliver between the rung's
ceiling and the next whole millisecond, which tonic would still spell in milliseconds. No plan can
land there: every knob the shell parses is a count of milliseconds and the grace added to it is
another.

`scripts/crosscheck.py` learns the bound, which is the question the deferral asked to have
answered. The adapter's contract quotes the number a future agent reads instead of the tree, so
`MAX_ANNOUNCED_DEADLINE_MS` joins `ANNOUNCED_DEADLINE_GRACE_MS` in `shippedcouplings.py` with
`docs/modules/body-rpc.md` as its far side. It is declared as a count of milliseconds rather than
a `Duration` for the reason the grace is: the scan reads an integer declaration and cannot read a
constructor call.

### Distrust green

The new wire case is `an_announcement_off_the_millisecond_rung_is_dropped_and_one_on_it_is_sent`
(`body/crates/rpc/tests/client.rs`), beside the existing
`a_deadline_the_header_cannot_spell_is_dropped_rather_than_sent`, which is kept: the two pin two
different facts about one drop, a duration the header cannot spell at all and one it spells in a
unit that reorders the clocks. The new case reads the truncation off `Request::set_timeout` itself
rather than off tonic's source, so a ladder that moves under a version bump reddens the case that
rests on it.

Mutation table, counts over `cargo test -p body-rpc --test client` (40 tests, all passing
unmutated):

| Mutation | Result |
| --- | --- |
| Ceiling raised back to the panic rung (`99_999_999 * 3_600_000`) | 39 passed, 1 failed: the seconds-band announcement is sent |
| Ceiling one millisecond low (`99_999_998`) | 39 passed, 1 failed: the announcement on the rung is dropped |
| Filter removed entirely | 38 passed, 2 failed: the seconds-band case, and the older case panics inside tonic's encoder |
| Boundary made exclusive (`<` for `<=`) | 39 passed, 1 failed: the announcement exactly on the rung is dropped |

The registry entry was mutated separately, over `just check-crosscheck` (71 constants, 81 sites,
238 mentions, green unmutated). Renaming the constant in `call.rs` alone failed with
"body/crates/rpc/src/call.rs declares no MAX_ANNOUNCED_DEADLINE_MS"; moving its value alone failed
naming `docs/modules/body-rpc.md` as the file that no longer spells the rendered needle, and
printing how far into it the match got.

### What this opens

Nothing new. The regime the encoding addendum filed is closed here.

## Host-shape addendum (2026-08-25): a dead address is the host's fact, so the retry proof counts attempts

The live check that measures this decision's patience failed on a machine where nothing about the
seam had changed. `the_probe_budget_bounds_a_down_verdict_against_a_dead_address` asserted
`probe_took >= 400ms`, the lower bound whose stated job was to prove the probe still retried, and
measured 251.4 / 251.6 / 251.6 ms against `http://127.0.0.1:1`. The same three digits came back at
a commit predating the session in a clean worktree, so the check had rotted rather than the code.

### Re-derived from the host before anything was decided

A raw socket, not the seam, answers why. A dial to `127.0.0.1:1` on this machine does not refuse:
it sits until the caller's own clock ends it (2001.9 / 2000.6 / 2001.5 ms against a 2 s socket
timeout). It is not every port, though, and the exception is the whole explanation: `45999` refuses
in 0.3 ms while `1`, `2`, `7`, `9`, `79`, `1023`, `1024`, `1234`, `8099` and `65000` all hang. This
distro's ephemeral range runs from 44620 to 48715 (`/proc/sys/net/ipv4/ip_local_port_range`), and
the one port measured inside it is the one that refuses. The reading that fits: under WSL's mirrored
networking the Linux stack answers for the ports it owns and the Windows host is handed the rest,
where nothing answers a SYN to a closed port at all.

So the check's own comment, "a refused dial returns long before its deadline, so what the clock
actually measures here is the one wait", is false on this host. The first attempt reaches its
250 ms deadline, the expiry is terminal, and the verdict is one attempt old rather than two: 251 ms,
dead flat, because it is a deadline rather than a network.

**A second check had the same premise and did not fail, it waited.**
`the_link_probe_classifies_the_live_brain_and_a_dead_address` probed the same address over a
**bare** client, with no decorator and therefore no deadline over it. libtest reported it running
past 60 s, and the suite took 133.54 s for what is otherwise about 6 s of work. Nothing in this
repo bounded that: the wait ended when the kernel stopped retransmitting the SYN.

### The question this had to answer first: is the terminal timeout the defect?

It is not, and the reasoning is worth writing down because the failing check makes it look like
one. The deadline addendum's three arguments are unmoved by anything measured here. What the new
evidence adds is a fourth, from the other end of the plan: the same classification governs the
reads, and making an expired deadline retryable would give a `list_sessions` against a wedged brain
five attempts of a 5 s deadline, 25 s of attempts and 6 s of waits, which is the load amplifier
stated in the abstract, now with a number on it.

And the honest account of what the probe loses on a host that drops dials is small. `Down` is true
at 251 ms and would still be true at 900 ms; what is not spent is one reconnect chance inside a
single probe. The indicator does not depend on that chance, because the overlay re-checks every 5 s
while it is visible and not ready (ADR-0011 indicator addendum), so the reconnect window survives
outside the probe rather than inside it. The bound the dot advertises is unaffected either way:
`Down` still arrives within `max(probe_budget, probe_deadline)`.

`RetryPolicy::within` is likewise sound as written. It prices an attempt at its full deadline,
which is an upper bound under both host shapes; where dials are dropped it over-provisions and the
probe answers early, which is the direction a bound is allowed to be wrong in.

**So no production code changes here.** What changes is what the checks measure.

### Decision 1: patience is proven by counting attempts, off a peer the suite owns

A wall clock cannot tell "two refused dials with a 400 ms wait between them" from "one attempt that
spent its deadline". Nothing about that is fixable by choosing a better number, because the two
shapes differ in what happened rather than in how long it took. So the proof moves to a count.

`dial_dropping_peer` (in the live suite) binds `127.0.0.1:0`, accepts every dial, drops it without
a word, and counts. Every attempt fails `Connection` in about a millisecond on any host, since the
peer is a socket this process owns rather than a hole in somebody's network stack, and tonic opens
exactly one TCP connection per attempt, so the counter is the attempt count read off the wire.
`the_probe_trims_its_attempts_where_a_read_spends_them_all` then asserts the whole promise in one
place: the probe spends exactly 2 attempts with one real 400 ms wait between them, and the same
schedule leaves the read all 5. That is strictly more than the assertion it replaces, which could
only say that some time had passed, and it is the first check anywhere to pin the claim the probe
budget exists for, that raising the read knobs never drags the probe along with them.

### Decision 2: the dead address keeps the bound and gives up the lower bound

`127.0.0.1:1` stays, because it is the one peer no fixture can imitate: nothing listening at all.
Its check now asserts `Down` and a verdict inside the budget, and nothing else. The cost is the
host's to decide, the bound is ours, and a check should assert the half it owns.

### Decision 3: an undecorated probe is never pointed at a peer that can hang

The bare-client check moves to the dropping peer entirely, and its name says so:
`the_link_probe_classifies_the_live_brain_and_a_peer_that_cannot_serve`. A client with no
decorator has no
deadline by design, the clock living in the decorator, so pointing one at a closed port makes the
suite's own runtime a fact about the host too: two minutes here, milliseconds on a Linux stack, and
in neither case a measurement of anything this repo wrote. It keeps its claim, that a probe
classifies rather than raises, and gains an assertion that the peer was really dialed, so it cannot
pass by never reaching it. The live suite goes from 133.54 s to 6.41 s.

### Distrust green

Mutation table, counts over `cargo test -p body-rpc --test live -- --ignored` (8 checks, all
passing unmutated against a brain served with a token):

| Mutation | Result |
| --- | --- |
| The probe's schedule is not trimmed to its budget | 7 passed, 1 failed: "the probe made 5 attempts on a 5-attempt schedule trimmed to a 1 s budget" |
| The probe never retries (`RetryPolicy::ONCE` for `Health`) | 7 passed, 1 failed: "the probe made 1 attempts" |
| The reads are trimmed like the probe | 7 passed, 1 failed: "the read made 2 attempts of the 5 its schedule allows" |
| A refused dial is terminal (`is_transient(Connection)` false) | 7 passed, 1 failed: "the probe made 1 attempts" |
| An expired deadline draws `Degraded` | 7 passed, 1 failed: the dead address, which is the shape this host produces |
| A refused dial draws `Degraded` | 6 passed, 2 failed: both peers that cannot serve |

The fourth and the second are the same failure by two routes, and together they are the answer to
"does this still fail if the probe stops retrying": it does, in 0.25 s, by count rather than by
clock. The fifth is the one that says the dead address still bites on this host, where its verdict
comes from the deadline.

The two clock bounds that remain were then measured under load rather than at idle, since a bound
read on a quiet box says little about the one a busy box will produce: with 48 spinners on 24 cores
(1-minute load average 13.97 by the end of the sweep) the counted check passed three times at
6.46 / 6.45 / 6.45 s against 6.41 s idle. It is dominated by sleeping rather than by working, which
is why saturating the box barely moves it, and both bounds keep more than a second of slack.

The failure this pass started from was also reproduced at a commit predating it, in a clean
worktree: 251.637515 ms, against the 400 ms the check demanded. The rot is older than the session
that found it.

### Consequences

- No production code changed. The retry gate, the transient set, the trimming arithmetic and every
  deadline are exactly as the deadline addendum left them.
- The live suite is bounded on every host: no check in it waits on a peer that may never answer.
- A future reader who measures a probe against a dead address and gets a number below the first
  backoff has not found a regression. The two shapes are written down here, and the count is where
  the answer lives.

### What this opens

Nothing in the transport. The one deferral filed alongside this pass is about the record rather
than the seam: nothing holds the roster of live checks in
[docs/modules/body-rpc.md](../modules/body-rpc.md) to the checks the file actually carries, and it
had drifted to "two" while seven were running
([R-442](../refinements/tasks/442-nothing-holds-the-live-check-roster-to-the-suite.md)).
