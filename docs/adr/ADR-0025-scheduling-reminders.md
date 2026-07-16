# ADR-0025: Scheduling & proactive reminders (`ScheduleStore`, the ticker, and delivery over both seam directions)

- **Status:** Accepted (Slice 9.5)
- **Date:** 2026-07-08

## Context

Slice 9.5 gives the assistant a sense of time: "remind me at 18:00 to stretch", "every
morning summarize my inbox". Schedule now, fire later, with the brain acting on its own
initiative. The ROADMAP scoped it as a `ScheduleStore` port, a native `schedule_task`
tool through the audited `ToolRegistry`, a pure use-case deciding what is due, and two
firing modes: an **autonomous task** run via a subagent (Slice 7), and a **reminder**
delivered to the user, pull-first (surfaced when the overlay next opens), proactively
over the **brain→body** direction Slice 9 just opened. (The ROADMAP's "Design → ADR-0014"
pointer was stale, since 0014 was taken by history windowing in the 2026-07-03 insertion wave;
this slice's ADR is 0025 and the pointer is fixed alongside it.)

Facts that shape the design:

- **The one hard rule is the headline.** A schedule *outlives every model swap* and
  every brain restart. Nothing may live in the orchestrator process beyond the in-flight
  fire; every `ScheduledItem` lives in the external store, and firing is a stateless
  read-store → act → persist pass (the ROADMAP names this the gate the slice proves).
- **The stack's Redis is already the durable-enough tier.** The base compose runs Redis 8
  append-only on a named volume; *sessions*, conversation history, the thing the hard
  rule exists to protect, already live there. A Redis `ScheduleStore` has the same
  durability class; a Postgres twin stays a pure adapter swap behind the port (the
  ROADMAP's "Redis for near-due, Postgres for durable" split becomes a deferral, not a
  v1 requirement, so scheduling does not couple to the memory overlay).
- **Every mechanism the slice needs has a worked precedent.** The dispatcher's taint
  stamp on `ToolCall` rides onto persisted work (`SubagentTask.tainted`, ADR-0018); a
  built-in tool is a `BuiltinTool` merged by `CompositeToolRegistry` and audited by
  `ToolDispatcher` (ADR-0010); the injected `Clock` port exists (sync, tz-aware); the
  shared contract-check suite pattern spans the in-memory fake and the fakeredis-covered
  adapter (`task_contract.py`); read-only overlay views are unary `BrainService` RPCs
  (ADR-0021); the brain→body call path is `BodyGateway` → `BodyService` (ADR-0023).
- **Two naming landmines.** `Scheduler` already means resource *admission* in this
  codebase (`SubagentScheduler` port, `ResourceBudgetScheduler`), and `scheduler.py`
  exists in `cortex_core`. The time-based machinery is named **`ScheduleTicker`** /
  `schedule.py` throughout. Never "Scheduler".
- **Autonomous firing has nobody to ask.** A fired item executes outside any live turn:
  there is no stream, no `Confirmer`, no user watching. The safety posture must be
  structural (what the firing path *cannot reach*), not conversational. It must
  extend to what the firing path *can be told to do* (decision 3's tainted-task refusal).

The draft of this ADR was adversarially reviewed pre-implementation (four lenses covering
crash/state/time, security/taint, seam/gates, operational completeness, with 27 findings).
Every major finding is folded into the decisions below: the finish-fencing claim token,
cancel-sticks-through-a-fire, corrupt-record quarantine, the tainted-task creation
refusal, fire-time outcome taint, the model-learns-"now" mechanism, the store-absent RPC
posture, and the `build_cortex_tools` argument-ceiling refactor.

## Decision

### 1. `ScheduledItem` + `ScheduleStore`: durable schedules behind a fenced port

Frozen, slotted values in `cortex_core/schedule.py` (new module, since `scheduler.py` is
taken by admission; `FireOutcome`/`ScheduleClaim` live here too, since `ports.py` is
protocols-only by contract):

```python
class ScheduleKind(Enum):    REMINDER = "reminder"; TASK = "task"
class ScheduleStatus(Enum):  PENDING = "pending"; FIRING = "firing"; DONE = "done"

@dataclass(frozen=True, slots=True)
class ScheduledItem:
    id: str
    kind: ScheduleKind
    text: str                      # reminder text, or the task instruction
    session_id: str                # origin session (provenance + future targeting)
    due_at: datetime               # tz-aware (enforced in __post_init__, Message precedent)
    created_at: datetime           # tz-aware (enforced)
    every: timedelta | None = None # None = one-shot; else fixed interval, must be > 0 (enforced)
    model: str | None = None       # task-only roster hint (ADR-0018; resolve() still rules)
    tainted: bool = False          # creation taint, OR'd with fire-time taint at finish()
    status: ScheduleStatus = ScheduleStatus.PENDING
    deliverable_since: datetime | None = None  # reminder fired, awaiting delivery/ack
    last_outcome: str | None = None            # last fire's result line (task) or None

@dataclass(frozen=True, slots=True)
class ScheduleClaim:
    item: ScheduledItem            # as of the claim (status FIRING)
    token: str                     # fencing token minted per claim; finish/release require it

@dataclass(frozen=True, slots=True)
class FireOutcome:
    fired_at: datetime
    next_due: datetime | None      # None → terminal (DONE); else re-armed PENDING
    deliverable: bool              # reminder awaiting delivery (sets deliverable_since)
    outcome: str | None = None     # persisted to last_outcome
    tainted: bool = False          # the fire consumed untrusted content; OR'd onto the item
```

The port (in `ports.py`; `ScheduleStoreError` joins `errors.py`):

```python
class ScheduleStore(Protocol):
    async def add(self, item: ScheduledItem) -> None: ...
    async def get(self, item_id: str) -> ScheduledItem | None: ...
    async def list_active(self) -> Sequence[ScheduledItem]: ...   # PENDING/FIRING + deliverable, due order
    async def cancel(self, item_id: str) -> bool: ...
    async def claim_due(self, now: datetime, *, lease: timedelta, limit: int) -> Sequence[ScheduleClaim]: ...
    async def finish(self, claim: ScheduleClaim, outcome: FireOutcome) -> bool: ...
    async def release(self, claim: ScheduleClaim) -> bool: ...    # un-claim: FIRING → PENDING, due unchanged
    async def deliverable(self) -> Sequence[ScheduledItem]: ...   # fired reminders awaiting ack
    async def ack(self, item_id: str) -> bool: ...                # delivered; False if not deliverable
```

The transitions are **guarded and fenced** (review findings showed a bare `finish(item_id)`
loses races it cannot even detect):

- **`claim_due`** claims items whose `due_at <= now` plus `FIRING` items whose lease
  expired (a crash or an overrun mid-fire), **oldest-due-first across both classes**,
  at most `limit`; each claim carries a fresh fencing `token`. Firing is therefore
  **at-least-once**: a brain that dies between claim and finish re-fires after the lease,
  never losing the item; deliveries and task runs may rarely duplicate (documented, since a
  lost reminder is worse than a repeated one). A record that fails to decode is
  **quarantined** (dropped from the live indexes to a dead-letter key, logged loudly
  naming it) and the rest of the pass proceeds. This is fail-loud-per-item, never a poison pill
  that halts all scheduling forever (the adapter-level twin of the session store's
  fail-loud read, adjusted for this port's whole-subsystem blast radius).
- **`finish(claim, outcome)`** applies only while the item is still `FIRING` under
  `claim.token`; it returns `False` (a logged no-op) for a stale claimant, so a task
  that outran its lease cannot clobber the re-claim's newer state, resurrect an acked
  reminder, or overwrite a fresher outcome. A matching finish persists
  `last_outcome`/`deliverable_since`, ORs `outcome.tainted` onto `item.tainted` (a
  *clean-created* task whose subagent read untrusted content at fire time must not
  launder that into a trusted listing), and re-arms to `PENDING` at `next_due` or,
  with `next_due=None`, goes `DONE` and is **deleted immediately unless deliverable**
  (terminal records never accumulate; a deliverable one-shot survives until `ack`).
- **`cancel` sticks.** It removes the item outright, whether pending, firing, or
  fired-but-undelivered (clearing deliverability), returning `True` when it stopped
  anything and `False` for an unknown id. An in-flight fire's later `finish` then finds
  no claim to match and no-ops `False`: a user's cancel can never be silently undone by
  a re-arm racing it.
- **`release(claim)`** is the graceful-shutdown un-claim: `FIRING` under the token →
  back to `PENDING` with `due_at` unchanged, so an orderly SIGTERM mid-pass does not
  strand claimed items for the full lease (a redeploy would otherwise delay a due
  reminder by up to `CORTEX_SCHEDULE_LEASE_S`).
- **`ack`** clears deliverability; on a `DONE` one-shot it deletes the record.

`InMemoryScheduleStore` lands in `cortex_core/fakes_schedule.py` (`fakes.py` is at
282/300), contract-checked by a shared `schedule_contract.py` suite (including the
guarded-transition races: stale finish rejected, cancel-during-fire sticks) that the
Redis adapter must also pass; quarantine is adapter-mechanics, tested on the adapter
with a deliberately corrupt record.

### 2. Recurrence (pure): one-shot + fixed interval, coalesced catch-up

`every` is a plain `timedelta`; `ScheduledItem.__post_init__` enforces `every > 0` (the
value invariant, while the 60 s floor is tool-boundary policy, decision 3). The pure helper
in `schedule.py`:

```python
def next_due(due_at: datetime, every: timedelta | None, now: datetime) -> datetime | None
```

returns `None` for one-shots, else the first anchored occurrence strictly after `now`,
so occurrences missed while the brain was down **coalesce into the single fire that just
happened** (one catch-up reminder, not a flood). Wall-clock time reaches the core only
through the existing `Clock` port. Local-time daily/weekly recurrence (DST-aware) and
cron expressions are deferred behind the same field, since an interval covers "every N
hours/days" reminders without a new dependency in the pure core.

### 3. Three cortex-only built-ins through the audited dispatcher

`schedule_task` (the ROADMAP's name, and one tool with a `kind` enum), `list_scheduled`,
`cancel_scheduled`, in `cortex_core/schedule_tools.py`, registered via the composition
root's builtins list, so they are **cortex-only by construction** (subagents never see
built-ins, ADR-0010/0013): a subagent cannot re-schedule, which bounds
self-perpetuation exactly like depth-1 bounds delegation fan-out.

- **The model learns "now" from the spec.** `ToolSpec`s are rebuilt on every
  `describe_tools` walk (the spawn tool's roster-derived spec is the precedent), so
  `schedule_task`'s *description* carries the current UTC time from the injected
  `Clock`, so the model can compute an absolute `at` for "at 18:00" without any engine or
  context-assembly change. Without this the headline use case is unimplementable: no
  existing context line tells the model the date or time (review blocker).
- **Arguments.** `{kind: "reminder"|"task", text, at?: ISO-8601-with-offset,
  in_seconds?: number, every_seconds?: number (≥ 60), model?: roster name}`, with exactly
  one of `at`/`in_seconds`. A **naive `at` (no offset/Z) is rejected** as `is_error`
  (the spec states times are UTC and shows the format; a configured display timezone is
  deferred, since v1 is UTC end-to-end, stored tz-aware and rendered ISO-8601 UTC).
  Validation failures return `is_error` results, never raise (volume.py precedent,
  including the bool-is-not-a-number and huge-int guards). Ids are uuid4 via an
  injectable factory (spawn precedent).
- **Two creation bounds** (the review noted "ungated + unbounded" invites a planted perpetual
  workload): active items are capped (`CORTEX_SCHEDULE_MAX_ACTIVE`, default 32; at the
  cap creation is an `is_error` naming the cap), and (the sharp one) **a tainted turn
  cannot create a `kind="task"` item at all** (refused as a trusted `is_error`). A
  reminder may carry attacker-influenced text because it only ever reaches a human; an
  *autonomous agent instruction* authored by injected content is a standing directive
  the runner would feed to a subagent as its user message. The structural gate below
  bounds what it can reach, but not what it is told to do. Deterministic, the ADR-0017
  spirit: the safety decision never rests on the model's judgment. Creation taint still
  stamps `ScheduledItem.tainted = call.tainted` for reminders (ADR-0018 mechanism).
- **Trust.** Creation/cancel results are `Trust.TRUSTED` and **never echo the stored
  text**. They confirm by id, kind, and ISO-8601 UTC time only, so a tainted-created
  reminder's text (and any URL in it) cannot ride back on a trusted result.
  `list_scheduled` does echo text, with one line per item: `{id, kind, due ISO-8601 UTC,
  every, tainted marker, last_outcome, text}`, so the listing is `TRUSTED` only when
  every listed item is clean, else `UNTRUSTED` (spawn's aggregate rule): hostile text is
  fenced and re-taints the turn instead of laundering through a trusted tool result.
  `cancel_scheduled` takes `{id}` (echoed from a listing); an unknown id is an
  `is_error` result.
- **Honest advertisement** (spawn precedent): the spec offers `kind: "task"` and the
  `model` knob only when delegation is wired, as signaled by the spawn tool's presence in
  the composition root; a reminders-only deployment advertises reminders only.
- **Gating.** All three are ungated by default, since creating a schedule is reversible by
  construction (`cancel_scheduled` sticks, decision 1; the irreversible thing is the
  *fired action*, where decision 4's posture lives). The `CORTEX_TOOLS_GATED` dispatcher
  backstop covers any of them by name for a cautious user (ADR-0022).

### 4. Firing: the `ScheduleTicker` is a stateless poll loop in the orchestrator

There is no lifecycle-hook mechanism in `serve()`; the ticker is an asyncio task started
by `run_from_env` beside `await serve(...)` and cancelled in its `finally` (the pump-task
discipline), with a done-callback that logs an unexpected death as an error. Every
`CORTEX_SCHEDULE_POLL_S` it runs one stateless pass: `claim_due(now, lease, limit)` →
fire the claimed batch concurrently (`asyncio.gather`, spawn precedent) → `finish` each
with `next_due` from decision 2. Each pass is wrapped in a structured-logged catch-all
(`except Exception: log + continue`) so an unenumerated bug degrades to a skipped pass,
never a silently dead ticker; `CancelledError` propagates, and on the way out the ticker
**releases** any claims it has not finished (decision 1) so a graceful shutdown strands
nothing. The ticker holds **no state**. Kill it anywhere and the store's lease recovers
the pass (the hard rule, live).

- **`REMINDER`** → `finish(deliverable=True, …)`, then a push attempt (decision 6);
  push failure leaves it deliverable for pull (decision 5).
- **`TASK`** → dispatched as a **synthetic `spawn_subagents` call through the ticker's
  own audited `ToolDispatcher`** (a private `CompositeToolRegistry` holding just the
  spawn tool + `LoggingAuditSink` + `confirmer=None`): `dispatch(call,
  tainted=item.tainted)` gives the fire an audit line, the dispatcher's taint stamp
  (→ `SubagentTask.tainted` → ADR-0017 pins a tainted or tools-enabled fire to the
  injection-robust model), admission/placement, and the fail-closed gate. All of it comes free,
  with **no change to `build_subagents`' public shape** (the runner stays encapsulated;
  the review's exposed-runner alternative is thereby unnecessary). The result's content
  becomes `last_outcome`; its trust becomes `FireOutcome.tainted` (fire-time taint,
  decision 1). With no spawn tool wired (a durable TASK from an earlier config outliving
  a reconfig), the fire finishes with an `ok=False` outcome naming the gap. One-shot
  goes `DONE`, recurring re-arms, neither crashing the pass nor lease-cycling forever.
- **Safety posture is structural.** The autonomous path runs with `confirmer=None`
  (fail-closed: gated tools hard-deny) and subagents hold only `UngatedToolRegistry`
  (gated specs stripped, invocation refused). A scheduled item, however hostile its
  origin, **cannot reach `send_email` or any gated action**; there is no confirm-away
  window because there is nobody to ask. Decision 3's tainted-task refusal closes the
  remaining hole (attacker-*authored* instructions); this closes attacker-*reachable*
  actions. Together they are the Slice 6.5 "a reminder created from injected content
  must not silently fire an irreversible action" requirement, enforced by reachability
  rather than judgment.
- **Errors.** `ScheduleStoreError` → log + skip the pass (per-item corruption is already
  quarantined inside `claim_due`, so this is a store-down signal, not a poison record);
  `BodyGatewayError` on push → recoverable, reminder stays deliverable; a task failure
  is an `ok=False` outcome, never a ticker crash.

### 5. Pull delivery: two seam RPCs, the ADR-0021 pattern plus one narrow write

`proto/body.proto`, `BrainService`:

```proto
rpc ListDueReminders(ListDueRemindersRequest) returns (ListDueRemindersReply);
rpc AckReminder(AckReminderRequest) returns (AckReminderReply);

message ListDueRemindersRequest {}
message ListDueRemindersReply { repeated DueReminder reminders = 1; }
message DueReminder {
  string reminder_id = 1;
  string text = 2;
  int64 fired_at_unix_ms = 3;   // when it became deliverable
  bool recurring = 4;
  bool tainted = 5;             // untrusted provenance, so the overlay may badge it
  string session_id = 6;        // origin chat (all sessions are listed; see below)
}
message AckReminderRequest { string reminder_id = 1; }
message AckReminderReply { bool acked = 1; }
```

`ListDueReminders` is a read-only store view (ADR-0021 exactly) and is deliberately
**all-sessions**. A single-user assistant has one user to remind; `session_id` rides
along so the overlay can later offer "open the conversation this came from" without a
wire change. `AckReminder` is the one narrow, idempotent write the pull loop needs
(acking a non-deliverable id is a no-op `acked=false`, so a retried ack is harmless).
`ScheduleStoreError` aborts `UNAVAILABLE` (the session-reads precedent). **With no
`ScheduleStore` wired (the default `CORTEX_SCHEDULE_BACKEND=none`), `ListDueReminders`
answers an empty reply and `AckReminder` `acked=false`**. A schedule-free brain is
indistinguishable from one with nothing due; it must never abort `UNAVAILABLE`, which
the body's `RetryingTransport` classifies as transient and would turn every overlay open
into a retry-backoff storm (review). Turning the backend off with deliverables stored
strands them until re-enabled (runbook note). Body-side, `BrainTransport` grows the two
unary methods (+ a `DueReminder` core mirror), `RetryingTransport` forwards
`list_due_reminders` as idempotent (ack stays unretried v1), and the overlay surfaces
deliverable reminders when it opens, acking on dismiss, matching "surface due reminders when the
overlay next opens", the ROADMAP's pull-first fallback.

### 6. Push delivery: `BodyService.Notify` over the Slice 9 seam

```proto
rpc Notify(NotifyRequest) returns (NotifyReply);
message NotifyRequest {
  string title = 1;
  string body = 2;
  string reminder_id = 3;
  bool tainted = 4;   // symmetric with DueReminder, so the toast may badge provenance
}
message NotifyReply { bool shown = 1; }
```

`BodyGateway` gains `async def notify(*, title: str, body: str, reminder_id: str,
tainted: bool = False) -> bool` (`GrpcBodyGateway`; `InMemoryBodyGateway` grows it too
and **moves to `cortex_core/fakes_body.py`** (`fakes.py` has no headroom) with its
`cortex_core` re-export unchanged). The ticker attempts a push exactly when the body
gateway is wired (`CORTEX_BODY_BACKEND=grpc`, with no second knob); `shown` → the ticker
acks (a native toast *is* delivery); `false` or `BodyGatewayError` → the reminder stays
deliverable and pull covers it. Body-side is all compile-forced by the proto change,
so in the CI-gated half, not an afterthought: a new `Notify` OS trait joins
`AudioControl` in `body_core::os` (Linux/macOS stubs behind the coverage escape hatch),
the `body_rpc` server grows a second backend generic and the `notify` handler behind the
same `SeamTokenValidator`, both contract-tested over loopback. The Windows impl (a
native toast from the Tauri shell) is host-authored (like `WindowsAudioControl`) and
**must render `title`/`body` as inert escaped text** (toast templates are XML; injected
reminder text must not become actionable markup, per the seam's data-not-instructions
posture, extended to the host). If the Tauri toast outpaces the session it lands
host-side per the shape-now/implement-later seam precedent (`CaptureScreen`), recorded.

### 7. Config, wiring, and the Redis adapter

- **`ScheduleConfig`** in `config_schedule.py` (the `config_subagents.py` split
  precedent; `config.py` is at 224): `CORTEX_SCHEDULE_BACKEND` (`none` default, so CI and
  the no-service dev loop run schedule-free, the turn path byte-identical),
  `CORTEX_SCHEDULE_POLL_S` (5.0), `CORTEX_SCHEDULE_LEASE_S` (300),
  `CORTEX_SCHEDULE_CLAIM_LIMIT` (8), and `CORTEX_SCHEDULE_MAX_ACTIVE` (32). Redis
  location reuses `CORTEX_REDIS_URL`.
- **The builtins bundle.** `build_cortex_tools` already sits at the PLR0913 six-argument
  ceiling (per review, verified against ruff's counting), so the composition root's
  built-ins stop being individual parameters: wiring pre-assembles the builtins sequence
  (spawn, volume, schedule tools) via a `build_builtin_tools(...)` helper in
  `schedule_builders.py` and passes **one** sequence, which is the `TurnCapabilities`-style
  bundling the ruff config itself prescribes. `build_schedule(...)` returns
  `(ScheduleStore | None, closer)`; the ticker takes one frozen collaborators value.
- **`RedisScheduleStore`** in `cortex_session/schedules.py`: schedules are **durable** with
  no TTL (the `RedisTaskStore` `ex=3600` would silently drop reminders), records carry
  the session store's `{"v": 1, "kind": "schedule"}` version markers with
  lenient-extra-keys / loud-unknown-kind decode (the durable-record evolution policy);
  an undecodable record on the claim path is quarantined per decision 1 (elsewhere, in
  `get`/`list_active`, where it fails loudly naming its key, the one-record blast radius).
  Keys: `cortex:schedule:{id}` (JSON, claim token included) + the ZSET indexes
  `cortex:schedules:due` (score = due-at epoch), `cortex:schedules:firing` (score =
  claim epoch, the lease), `cortex:schedules:deliverable` (score = fired-at epoch), and
  the dead-letter `cortex:schedules:dead`. Index+record write pairs go through a
  pipeline; every `RedisError` wraps into `ScheduleStoreError` with the cause chained.
  100% via fakeredis through the shared contract suite; an `integration`-marked live
  test replays the checks against real Redis.

## Consequences

**CI-gated (mine, 100% under `just check`, no Redis/GPU/OS/GUI):** the values + port +
pure `next_due` + `InMemoryScheduleStore` + the contract suite (guarded transitions and
races included); the three built-ins through a real `ToolDispatcher` (audit, taint
stamp + tainted-task refusal, trust rules, the clock-bearing spec, honest
advertisement, both creation bounds); `RedisScheduleStore` over fakeredis (quarantine
included); the `ScheduleTicker` over the fakes with an injected clock (no sleeps, since the
poll wait is injected, asserted with a fake); the proto extension regenerated into both
committed stub trees, the facade re-exports, the two `BrainService` handlers (store-
absent behavior included), `BodyGateway.notify` + both adapters + the `fakes_body.py`
split; the body-side `Notify` OS trait + stubs + the `body_rpc` `notify` handler and
its loopback contract tests; the Rust `BrainTransport` reminder methods + retry
forwarding + fake-brain contract tests; the overlay's reminders-on-open surface over
its fake bridge.

**Agent-Docker (mine):** the schedule contract suite against live Redis; an
`integration`-marked end-to-end fire. Seed a near-due reminder, watch the ticker make
it deliverable, read it back over `ListDueReminders`, ack it, all against the real brain +
Redis containers.

**Host-Windows (host-only):** the native toast (the Tauri-shell `Notify` impl over the
new OS trait, rendering reminder text inert) and the overlay's reminder surface on the
real hotkey→overlay path (runbook `docs/runbooks/scheduling.md`).

**Deferrals** (recorded in the ROADMAP's deferred-refinements section): the Postgres
durable twin behind the unchanged port; local-time/cron recurrence and a display-
timezone knob (v1 is UTC end-to-end); occurrence history (coalesced single-slot
deliverability keeps no per-fire records, and terminal cleanup deletes a one-shot
task's outcome with the record); snooze/edit verbs; task-outcome delivery as a
notification; a push retry policy beyond next-poll-pull; structured provenance beyond
the `tainted` bit; overlay badge/UX polish for tainted reminders; retention/inspection
tooling for the dead-letter key.

## Alternatives rejected

- **Postgres-first store.** Couples scheduling to the memory overlay for no durability
  win the stack doesn't already grant sessions (AOF + named volume); the port keeps the
  swap pure when per-provenance queries or retention policies earn it.
- **Cron-string recurrence (croniter).** A new dependency in the pure core for
  expressiveness no near-term reminder needs; the `every` timedelta covers the real
  cases and the field carries a richer rule later.
- **Per-occurrence delivery records.** A second entity and a growth policy, to preserve
  duplicate fires nobody reads at personal scale; coalescing into the item's one
  deliverable slot is simpler and loses only history (deferred).
- **Delivery as a new `ServerEvent` on `Converse`.** Per-stream: the overlay must hold
  an open stream to hear it, and reminders outlive streams by design. Pull RPC + body
  push are both stream-independent.
- **A scheduling sidecar process.** A new deployment unit and seam for no isolation win;
  the orchestrator already owns an asyncio lifecycle, and the ticker is stateless by
  construction so process placement is immaterial.
- **Exposing the `SubagentRunner` from `build_subagents` for the ticker.** The ticker
  dispatches a synthetic `spawn_subagents` call through its own audited dispatcher
  instead. That gives the audit trail, taint stamping, and the fail-closed gate for free, and the
  builder's public shape (and its tests) stay untouched.
- **Fencing via status checks alone (no claim token).** A status guard cannot tell the
  original claimant from the re-claim (both see `FIRING`), so a late finish would still
  clobber; the token is one field and one parameter.
- **Naming it `Scheduler`.** Collides with the resource-admission vocabulary
  (`SubagentScheduler`, `ResourceBudgetScheduler`, `scheduler.py`) in the same flat
  export namespace.

## Risks

- **At-least-once duplicates.** A crash between claim and finish re-fires after the
  lease: a reminder may toast twice, a task may run twice. Accepted (personal scale;
  losing fires is worse); the lease bounds the window, the fencing token bounds the
  damage (a stale finish is a no-op), and graceful shutdown releases claims so the
  common restart path is prompt, not lease-delayed.
- **Lease vs. long tasks.** A task outrunning `CORTEX_SCHEDULE_LEASE_S` gets re-claimed
  while still running (a duplicate run; the stale finish is fenced off). The default
  (300 s) sits far above measured subagent latencies; the knob exists, and the risk is
  noted in the runbook.
- **A tainted recurring reminder is a standing lure.** Its text is fenced on every
  model-facing surface and badged on both wire paths, but a human can still read and
  obey it; the tainted-task refusal keeps it from becoming autonomous compute, and the
  active-items cap bounds the volume an injected turn can plant.
- **Push-acked ≠ seen.** A toast shown while the user is away still acks. Accepted: a
  toast is the OS's delivery contract; unseen-toast recovery (history) is the deferred
  occurrence-history item.
- **Ticker vs. turn contention.** Fires share the process with live turns; the claim
  limit bounds a pass, and subagent admission (ADR-0012) already budgets the heavy part.

## Addendum (2026-07-08): the brain half landed + agent-Docker validation

The CI-gated brain half is implemented across four commits (store layer → built-ins →
seam → ticker/wiring), 100% line+branch across the workspace at every commit, with two
small implementation refinements to the shapes above: `ScheduledItem.model` is `str = ""`
(the `SubagentTask` convention, where `""` is the default roster entry) rather than
`str | None`, and `ScheduleStatus` has no `CANCELLED` member (decision 1's cancel-deletes
semantics made it unreachable; `DONE` persists only while deliverable).

**Agent-Docker validation (same day), against the rebuilt compose stack
(`CORTEX_SCHEDULE_BACKEND=redis`):**

- the fenced-protocol **contract suite passed against live Redis** (all checks; the run
  guards against and cleans up after itself, per [scheduling.md](../runbooks/scheduling.md));
- the **end-to-end fire round-tripped over the live seam**: a reminder seeded directly
  into the store was fired by the brain's ticker, listed over `ListDueReminders` (text,
  recurrence, provenance, and origin session intact), acked over `AckReminder`, and a
  second ack no-opped `acked=false`;
- `just seam-health` confirmed the rewired turn path still converses (Health, one full
  `Converse` turn, and the session reads all green against the same containers).

Remaining in-slice, behind the committed seam shapes: the Rust `BrainTransport` reminder
methods + retry forwarding, the overlay's reminders-on-open surface, and the body-side
`Notify` trait + Tauri toast (host-validated). Then comes the multi-agent adversarial review
of the landed diff, recorded below when its findings are folded.

## Addendum (2026-07-08): post-implementation adversarial review (11 findings, all fixed)

A second multi-agent adversarial review ran over the landed diff (four lenses covering races,
security/taint, contract honesty, wiring, with each finding independently verified against the
committed code; 13 findings, 11 confirmed, 2 refuted). Every confirmed finding is fixed:

- **The fenced transitions are now optimistically atomic** (the review's sharpest find:
  `finish`/`release`/`ack`/claim were check-then-act across two Redis round-trips, so a
  cancel landing between a guard read and its write was silently overwritten, so a cancelled
  recurring task could resurrect). Every guarded transition now runs its guard and write in
  one WATCH→MULTI/EXEC transaction (`schedule_claims.py`, split out for the cap): a raced
  EXEC fails as `WatchError`, answered exactly like a stale token. Deterministic race tests
  poke a concurrent cancel/touch into the guard window and pin all four transitions.
- **Fires are bounded by the lease** (a wedged inference socket or saturated admission
  budget in one TASK fire would have blocked the strictly serial ticker, and every
  later-due reminder, for the process lifetime, with the documented overrun re-claim
  unreachable in-process). `run_once` wraps each fire in `wait_for(lease)`: a hung fire is
  cancelled and its claim released for the next pass.
- **`CORTEX_TOOLS_GATED` now covers the autonomous path**: the ticker's private spawn
  dispatcher takes the gated set, so a user-gated `spawn_subagents` hard-denies on a
  scheduled fire (no confirmer exists to ask) instead of silently bypassing the backstop.
- **`next_due` is total**: an occurrence past `datetime.max` ends the recurrence (None)
  instead of raising into a forever lease-cycling item, and `every_seconds` gained a
  ten-year ceiling at the tool boundary, which closes the planted-overflow starvation vector.
- **Test honesty**: the quarantine test now puts the poison FIRST (a halt-the-pass
  regression fails it); the clock-bearing spec's per-walk rebuild is asserted with a
  stepping clock through the full dispatcher chain; cross-class oldest-due-first joined the
  shared contract; and a composition-root test runs `run_from_env` with
  `CORTEX_SCHEDULE_BACKEND=redis` end to end (env → store → ticker fire → pull RPC →
  SIGTERM shutdown). The two refuted findings (compose pacing passthrough; a duplicate of
  the WATCH find) are recorded as such.

The Docker validation was re-run against the rebuilt stack after the fixes. The
"CI-gated" Consequences list above reads as the slice-total ledger; the previous addendum
names what of it still remains (the Rust transport methods, the overlay surface, the body
`Notify` trait).

## Addendum (2026-07-12): `snooze` joins the fenced verb set

The deferred snooze verb lands behind the unchanged seams: one new fenced
`ScheduleStore.snooze(item_id, *, until)` transition plus a fourth cortex-only built-in,
`snooze_scheduled` (in `schedule_verbs.py`, split from `schedule_tools.py` with
`CancelScheduledTool` and the shared result helpers, since the line cap forces the
creation/listing vs lifecycle-verb split anyway). Decisions:

- **One-shots only.** `next_due` anchors recurrence on `due_at` (occurrences are
  `due_at + k * every`), so snoozing a recurring item by rewriting `due_at` would silently
  re-anchor the whole series (a daily 09:00 nudged ten minutes once becomes a daily 09:10).
  v1 refuses a recurring item with a correction naming the workaround (cancel and
  re-create); an anchor-preserving occurrence snooze (a separate anchor field, or an
  occurrence skip) is recorded deferred rather than drifting silently.
- **Two snoozable states.** A PENDING one-shot moves its `due_at` to `until` (the due index
  re-scored); a fired-but-undelivered one-shot reminder (DONE and deliverable, the
  snooze-the-toast case) re-arms to PENDING at `until` with deliverability cleared, so it
  fires fresh instead of re-delivering stale. FIRING refuses (the in-flight fire settles
  first) and unknown ids answer False. The transition is WATCH-fenced exactly like
  `finish`/`release`/`ack`: a racing cancel or claim fails the EXEC and snooze answers
  False, never a lost update.
- **The tool takes relative time.** `snooze_scheduled(id, for_seconds)` computes
  `until = now + for_seconds` from the injected Clock (snooze means "from now", and no
  clock arithmetic is demanded of the model); `for_seconds` reuses the same `[60 s, ten-year]`
  bounds the recurrence interval (`every_seconds`) enforces, via a `parse_for_seconds` beside
  the creation parser. (This is a deliberate floor, not a mirror of the one-shot `in_seconds`
  delay, which is unbounded above 0: a sub-minute snooze is below the poll granularity and
  unlikely to be wanted, and reusing the recurrence bounds keeps one number to reason about.)
  The tool reads the
  item first for a precise correction (unknown / recurring / firing now), then relies on
  the fenced transition for the race-free answer, so the read is advisory and the store is
  authoritative. No taint gate, matching `cancel_scheduled`: postponing an existing
  human-visible item is the same trust class as deleting it, and results never echo stored
  text.

CI-gated through the shared contract suite (fake + fakeredis interchangeably) and the tool
tests over the fake; the live Redis integration suite exercises the same contract on the
real backend (run 2026-07-12 by the agent against the compose Redis, passing).

**Claim re-check (post-review hardening).** The Redis claim path had a before-WATCH race an
adversarial review found: `claim_due` snapshots the due index, then WATCH-claims each
candidate one at a time. A `snooze` (or a recurring `finish`) committing *between* the
snapshot and a candidate's WATCH moves that record's due time forward, but WATCH fences only
writes landing *after* the watch, so the stale snapshot would still claim it and fire the
reminder at the old time, silently discarding the user-confirmed snooze. `_claim_one` now
re-checks the WATCH'd read (skip when a PENDING record's `due_at` is now in the future),
closing the window; a lease-expired FIRING candidate stays re-claimable, and a
cancelled/finished-away record already reads absent. The in-memory fake claims in one
synchronous block so it never exhibited the hole; the fix is proven by a Redis test that
commits the snooze from inside the due-snapshot call and asserts the item is skipped, its
future due-entry intact (it fails without the re-check).

## Addendum (2026-07-12): dead-letter inspection lands adapter-side

The quarantine hash gets its deferred inspection tooling as **`RedisScheduleStore` methods,
not port methods**: `dead_letters()` returns the quarantined `DeadLetter(item_id, raw)`
entries (id order, raw bytes rendered with replacement characters so corrupt content stays
inspectable and never crashes a second time), and `purge_dead_letter(item_id)` drops one for
good. Deliberately off the `ScheduleStore` port: quarantine is a codec mechanic of the Redis
claim path, the in-memory fake can never produce one (a port method would force a vacuous
fake), and no core path consumes dead letters. Operator-facing only, never a model tool: the
raw bytes are exactly the hostile or corrupt content the codec refused, and they stay
unparsed inspection data. The runbook shows the store calls and the redis-cli equivalents.
Retention stays manual, because the hash only grows when a record is quarantined, which is
exceptional; an automated policy joins the deferred ledger only if reality produces volume.
CI-gated over fakeredis (quarantine-then-inspect, hostile-bytes rendering, failure
wrapping); live-validated 2026-07-12 by the agent against the compose Redis (a corrupt
record planted, quarantined by a real claim pass, listed, purged, purge-again False).

## Addendum (2026-07-13): session attribution lands via the TurnStamp seam

The deferred session attribution landed as the first consumer of ADR-0027's structured
turn provenance: the dispatcher's per-call stamp widened from the lone taint bool to a
frozen `TurnStamp` (`session_id` + `tainted`), the engine threads the turn's session
through `ToolLoopContext`, and `schedule_task` now fills `ScheduledItem.session_id` from
`call.stamp` instead of `""`. The ticker's synthetic `spawn_subagents` dispatch stamps the
fired item's stored `session_id` and taint, so a task fire carries its origin chat onward
exactly as it already carried creation taint. No store, codec, or wire change: the field
and its round-trip existed since this ADR; only its source did not. The listing keeps not
rendering it (provenance, never display), and creation confirmations keep not echoing it.
Decision snippets above showing `call.tainted` and `dispatch(call, tainted=...)` predate
the rename and read with `call.stamp.tainted` / `stamp=TurnStamp(...)` applied.
CI-gated end to end (dispatcher stamp + forged-stamp discard, engine-to-item attribution
through a real dispatcher, the ticker's stamped fire).

## Addendum (2026-07-13): `edit` joins the fenced verb set

The deferred edit verbs (retext / re-recur without cancel-and-recreate) land behind the
unchanged seams, replaying the snooze slice: one new fenced `ScheduleStore.edit(item_id,
edit)` transition plus a fifth cortex-only built-in, `edit_scheduled` (in `schedule_verbs.py`
with its siblings). Decisions:

- **`due_at` is not editable; the recurrence is.** An edit changes `text` and/or `every`,
  never the next due time, so re-recur alters the cadence of *future* re-arms only and the
  imminent occurrence is never silently moved (the very re-anchoring hazard that keeps
  `snooze` off recurring items). `every` is three-valued in the tool: a bounded interval
  sets/replaces it, the `0` sentinel stops repeating (one-shot), and omitting it leaves the
  recurrence alone. Because only the record changes (text/every/taint live in it, not the
  due/firing/deliverable indexes), the fenced transition is a bare watched `SET`, needing no
  `zadd`/`zrem` at all: the lightest of the guarded writes.
- **One pure `apply_edit`, both stores.** The change is expressed as a `ScheduleEdit`
  value (`text?`, `every` + `set_every`, `tainted`) applied by one pure `apply_edit` function
  the in-memory fake and the Redis helper both call, so they mutate an item identically (the
  ports-before-adapters guarantee) and the fenced-vs-plain difference is only the concurrency
  wrapper. FIRING refuses (the in-flight fire settles first) and unknown ids answer `False`,
  WATCH-fenced exactly like `finish`/`snooze`/`ack`: a racing cancel or claim fails the EXEC
  and `edit` answers `False`, never a lost update.
- **The taint gate is the one departure from cancel/snooze.** Unlike deleting or postponing
  an existing item, a retext *injects new content*, so the editing turn's taint ORs onto the
  item (never clearing it: the listing then badges it and re-taints on recall, the aggregate
  rule), and an autonomous **task** cannot be edited on a tainted turn at all, matching the
  creation-side tainted-task refusal (a task instruction authored by injected content is a
  standing directive, not a reminder a human vets). A reminder edit on a tainted turn is
  allowed, its text only ever reaching a badged human. The refusal is deterministic (the
  dispatcher's stamp on `edit.tainted`, never a model claim). Results stay `TRUSTED` and
  never echo the stored text (`edited <id>`), matching the sibling verbs.

CI-gated through the shared contract suite (fake + fakeredis interchangeably: retext,
set/clear recurrence, taint monotonicity, FIRING/unknown refusal, the WATCH-fence race) and
the tool tests over the fake (parsing matrix, the tainted-task refusal, the tainted-reminder
allowance, down-store wrapping); the live Redis integration suite exercises the same contract
on the real backend. Remaining deferred at the time: an anchor-preserving occurrence snooze
still wanted the same separate-anchor field this verb deliberately did not add. That field
lands in the addendum below.

## Addendum (2026-07-13): anchor-preserving occurrence snooze

`snooze` now works on recurring items, closing the deferral the original snooze addendum and
the edit addendum both named. The hazard those addenda avoided was real: `snooze` rewrites
`due_at`, and because a recurring item's occurrences are `due_at + k*every`, moving `due_at`
would silently re-anchor the *whole series*. The fix is the separate-anchor field the edit
verb deliberately did not add, added here for exactly this transition. Decisions:

- **`anchor` pins the grid origin; `due_at` stays the next fire.** `ScheduledItem` gains an
  optional `anchor: datetime | None` (default `None`). Everything continues to index and claim
  on `due_at` (unchanged), so the field is inert for one-shots and unsnoozed recurring items.
  The ticker's two re-arm sites now compute `next_due(recurrence_base(item), item.every, ...)`
  where `recurrence_base` returns `anchor` when set, else `due_at`. So a snoozed recurring item
  re-arms on its original cadence (`origin + k*every`) rather than drifting to `until + every`.
- **One pure `apply_snooze`, both stores.** Mirroring `apply_edit`, the transition is a single
  pure function the fake and the Redis adapter both call: it sets `due_at=until`, status
  `PENDING`, clears `deliverable_since`, and, *only for a recurring item on its first snooze*,
  pins `anchor` to the pre-snooze `due_at` (a later snooze keeps the existing anchor, never
  re-pinning). The stores drop `every is not None` from their refusal, keeping only the FIRING
  and unknown guards; the fenced WATCH/MULTI wrapper is otherwise untouched. The
  `SnoozeScheduledTool` loses its recurring refusal and advertises the occurrence semantics.
- **A forward-compatible additive record field.** `anchor` rides the durable schedule record
  under the existing extra-keys policy: `encode` always writes it, `decode` reads it with
  `.get` so a record written before this addendum (no `anchor` key) decodes as `None`. No
  version bump; no migration.
- **Taint is untouched.** Unlike `edit`, a snooze injects no new content (it only postpones an
  existing human-visible item), so it keeps carrying no taint gate, exactly as before.

CI-gated through the shared contract suite (fake + fakeredis: the recurring snooze moves only
the next occurrence, pins `anchor`, round-trips the codec, and becomes claimable at the snoozed
time), the pure `apply_snooze`/`recurrence_base` unit tests, the tool test (recurring snooze now
succeeds and pins the grid), and a ticker test proving the re-arm follows the anchor grid, not
`due_at + every`; the live Redis integration suite exercises the same contract on the real
backend. Remaining deferred (unchanged): local-time/cron recurrence and the occurrence-history
table stay on the list; the anchor field is now the natural home for any future per-occurrence
override.

## Addendum (2026-07-14): a display timezone for model-facing schedule times

v1 rendered every model-facing datetime as ISO-8601 UTC, so a reminder came back as
`due 2026-07-22T18:00:00+00:00` to a user who thinks in local wall time. The deferral list
carried this as "local-time / cron recurrence and a display-timezone knob"; the **display half
lands here**, the recurrence half stays deferred (see the last decision). Decisions:

- **`DisplayZone` is a pure core value; the IANA lookup lives at the composition root.**
  `cortex_core/schedule_time.py` holds a frozen `DisplayZone(name: str, tz: tzinfo)` with
  `render(moment)` (the one canonical rendering, replacing the module-level `utc_str` that
  `schedule_verbs.py` shared) and `resolve(naive)` (the fold policy below). The core imports
  `tzinfo` from `datetime` and **never `zoneinfo`**: resolving a name to a concrete zone reads
  the system tz database, which is exactly the impure edge step adapters own. `UTC_DISPLAY` is
  the default value, so the v1 contract is what an unconfigured deployment still gets.
- **`CORTEX_SCHEDULE_TZ` is validated at boot, not at first render.** `ScheduleConfig.tz`
  (default `"UTC"`) is field-validated by resolving it through `zoneinfo`, so a typo like
  `Europe/Bucarest` fails the process at startup with the bad key named, rather than surviving
  as a latent error that only fires when the model first asks for a listing. The builder
  resolves the same validated name into the `DisplayZone` it threads into the three rendering
  built-ins (`schedule_task`, `list_scheduled`, `snooze_scheduled`).
- **The knob is passed through `docker-compose.yml`.** An env knob the container never receives
  is inert while every test stays green, which is the failure mode that has bitten sibling
  entries on this list. `CORTEX_SCHEDULE_TZ` joins the brain service's environment, and the
  runtime image was checked to carry a tz database (`python:3.12-slim-trixie` resolves 486
  zones), since `ZoneInfo` on a tzdata-less image would fail every non-UTC key.
- **The two hardcoded `(UTC)` spec strings become the configured zone.** Both strings the model
  reads are rebuilt per `describe_tools` walk: `schedule_task` advertises "the current date-time
  is `<rendered>` (`<zone name>`)" and `list_scheduled` advertises "due time (`<zone name>`)".
  Leaving these as literal `UTC` while the values rendered local would have been worse than no
  knob at all: the model would have read correct numbers under a false label.
- **The fold policy: a naive `at` now means display-zone wall time.** This is a **deliberate
  behavior change**. `_parse_at` rejected an offset-less `at` (`_NAIVE_AT`), correctly, because
  under a UTC-only render there was no defensible reading of a bare wall time. Once the model is
  shown local times it will write local times back, and a rejection costs a correction round trip
  the model may not recover from. So a naive `at` is now attached to the display zone, which is
  by construction the user's zone. `fold=0` resolves the two irregular cases deterministically:
  an ambiguous wall time (the hour repeated at a fall-back transition) takes the **earlier**
  offset, and a nonexistent one (the hour skipped at a spring-forward transition) is read with
  the **pre-transition** offset, landing just past the gap. An `at` that *does* carry an offset is
  honored exactly as before, so the model can always be explicit.
- **Both sides normalize to the instant, which implementation proved is not a no-op.**
  `resolve` returns the resolved wall time converted to UTC, and `render` hops through UTC before
  converting into the display zone. The second one looks redundant and is not: `datetime.astimezone`
  returns `self` unchanged when the input already carries the target zone, so rendering a
  freshly-resolved gap time printed `03:30+02:00`, a wall time that **never occurs**, while the
  same instant read back from the store (UTC in the record) printed the canonical `04:30+03:00`.
  The creation confirmation and a later `list_scheduled` would have disagreed about one item. With
  both normalizations one instant renders one way everywhere, and the store keeps receiving plain
  UTC instants exactly as it did before.
- **Recurrence is untouched, and DST-aware recurrence stays deferred for a stated reason.**
  Rendering is display-only: `ScheduledItem.due_at`/`anchor` remain UTC instants, the store,
  the codec, the fenced transitions and the ticker's grid arithmetic are all unchanged, and
  no migration exists because no record changed. The remaining half of the original entry is
  **not** the small change that entry implied: "daily at 09:00 local" cannot ride
  `ScheduledItem.every`, because `every` is a `timedelta` while a DST day is 23 or 25 hours
  long, so a fixed interval drifts off the wall clock exactly when a user would notice. That
  needs a new recurrence *shape* (a calendar rule beside the interval), not a knob, and it stays
  deferred with the cost recorded honestly.

CI-gated at 100% over the fakes: the renderer and the fold policy (including both DST
irregularities, against a real `ZoneInfo`), the config validator (good key, bad key, default),
the builder threading the configured zone into all three tools, and the tool-level assertions
that the spec strings and every rendered due time carry the configured zone. The default path
(`UTC`) keeps its existing assertions unchanged, which is the regression check that the knob is
additive.

## Addendum (2026-07-14): calendar recurrence, the second recurrence shape

The display addendum landed half of the original "local-time / cron recurrence and a
display-timezone knob" deferral and recorded honestly that the other half was not a knob.
It lands here. `every` is a `timedelta` while a calendar day is 23, 24, or 25 hours long, so
"every day at 09:00" expressed as `every=timedelta(days=1)` drifts by an hour at each
daylight-saving transition, which is exactly when a user notices. Decisions:

- **A structured `CalendarRule` beside the interval, not a cron expression.** A new pure core
  module `cortex_core/schedule_calendar.py` holds a frozen
  `CalendarRule(hour, minute, days: frozenset[int])` (weekday numbers, `date.weekday()`
  convention) plus `next_calendar_due(rule, after, zone)`. Cron was rejected on two counts: it
  needs a parser (a dependency, or roughly 150 lines of pure core that exists to serve one
  field), and it makes the *model* author `0 9 * * 1-5`, a syntax a small model gets subtly
  wrong in ways that validate fine. A named time plus a weekday list is the subset a personal
  assistant actually uses, and it stays a value the model can read back in a listing.
- **`days` is never empty, and every-day is the full set rather than a `None` sentinel.** One
  representation means one code path, and non-emptiness is load bearing rather than cosmetic:
  it is what bounds the occurrence search to a single week, so `next_calendar_due` terminates
  by construction instead of by a defensive iteration cap that could never be covered honestly.
- **`ScheduledItem` takes an interval or a rule and never both**, enforced in `__post_init__`.
  Two shapes on one record would make "how does this recur?" a reconciliation instead of a
  read, and `next_occurrence(item, now, zone)` (the new single entry point the ticker calls)
  can then answer by dispatch. `apply_edit` therefore **clears a rule whenever it sets
  `every`**: an edit that could not express the switch would have to fail, and keeping the rule
  while reporting the new interval would be worse. The `0` sentinel stops whichever shape the
  item had.
- **The rule carries no zone of its own; the deployment's `DisplayZone` is it.** The core stays
  `zoneinfo`-free exactly as the display addendum left it: the rule is pure wall-clock data and
  the zone arrives as the value the composition root already resolves. The consequence is
  deliberate and worth stating plainly: **changing `CORTEX_SCHEDULE_TZ` moves existing calendar
  schedules with it**, because "09:00" means 09:00 as this deployment renders time. For a
  single-user assistant that travels with its user, a 09:00 reminder that follows them is the
  wanted reading, and the alternative (a zone frozen onto each record at creation) would need
  the core to resolve IANA keys. A per-rule zone stays the additive extension if a second zone
  ever exists: a new field on the same value, not a different shape.
- **The first fire is derived from the rule, not asked for separately.** `at_time` is
  mutually exclusive with `at`/`in_seconds`, and `schedule_task` computes the first occurrence
  itself. The alternative (making the model supply both a due time and a recurrence, and keep
  them consistent) is the kind of two-field invariant a model silently violates. `on_days` is
  refused without `at_time`, and `every_seconds` alongside `at_time` is refused with a message
  naming the alternative, so neither can half-apply.
- **Daylight-saving policy is inherited, not invented.** Every candidate resolves through
  `DisplayZone.resolve`, so the two irregularities settle for a calendar occurrence exactly as
  they already settle for a naive `at`: an occurrence inside a **spring-forward gap** lands just
  past the gap (03:30 fires at 04:30 local: late, never skipped, because a reminder that
  silently does not happen on one day is worse than one an hour late), and one inside a
  **fall-back repeat** takes the earlier offset, so a repeated wall hour fires **once** rather
  than twice. One policy, one place, no second table of special cases.
- **A calendar item is self-anchoring, so snooze needed no new machinery.** The
  occurrence-snooze addendum's `anchor` pins an *interval* grid; a rule **is** its own grid, so
  a snoozed calendar item takes no anchor and `next_occurrence` returns it to its wall-clock
  cadence for free. The store transitions, the fencing, and `apply_snooze` are untouched.
- **The ticker reads the same configured zone the built-ins do**, threaded on `TickerSettings`
  rather than as a seventh constructor argument (the ruff `max-args = 6` injection ceiling, and
  the zone arrives from the very `ScheduleConfig` the pacing does). This is not rendering on
  that path: a calendar re-arm *is* wall-clock arithmetic, so creation and firing must read one
  zone or a rule would fire somewhere other than where it was scheduled.
- **The record key is additive, with no version bump.** `rule` encodes as a plain nested object
  and decodes with `.get`, the `anchor` precedent: a record written before this addendum has no
  `rule` key and decodes as absent. A rule that *is* present is read strictly, so a malformed
  one fails loudly like any other corrupt field rather than silently becoming a one-shot. No
  migration exists, because no existing record changed.

Four things implementation corrected or forced, recorded because each cost real work:

1. **The barrel had to be split first.** `cortex_core/__init__.py` sat at exactly the 300-line
   cap (its own recorded deferral), so this addendum could not export a single new public name.
   It now re-exports with the typing spec's redundant-alias form instead of restating every name
   in `__all__`, which halved it to 162 lines. That landed as its own commit ahead of this one.
2. **`schedule_args.py` hit the cap too**, and split along the line `schedule_verbs.py` already
   draws against `schedule_tools.py`: creation arguments stay put, the lifecycle verbs'
   arguments (`snooze`, `edit`) move to `schedule_verb_args.py`, importing the shared bounds
   from their sibling so "a legal interval" keeps one definition.
3. **The creation confirmation and the listing line now share one recurrence phrase.** They had
   drifted apart already ("recurring every 3600s" versus "every 3600s"), and a calendar rule
   would have needed the phrase written twice. Unifying them changed the creation wording, which
   one test pinned, and is the same class of divergence the display addendum caught between a
   creation confirmation and a later listing.
4. **The mutation pass caught an under-tested guard.** Reverting "read the *local* date, not the
   UTC date" left the suite green, because in a zone **ahead** of UTC starting the search a day
   early only adds candidates the strictly-after filter drops. It is observable only **west** of
   UTC, where the UTC date is already tomorrow: at 02:00 UTC on a Tuesday it is still Monday
   19:00 in Los Angeles, and reading the UTC date pushes a Monday 21:00 rule a full week out.
   The test now pins that direction.

CI-gated at 100% line and branch over the fakes, and every new guard mutation-proven (reverting
each one individually turns the new tests red): the strictly-after comparison, the local-date
read, the wrap-into-next-week candidate, the one-shape invariant, the edit's rule clearing, the
`next_occurrence` dispatch, and the ticker's zone threading. The daylight-saving cases run
against real `ZoneInfo` zones on both sides of UTC. The store contract suite gained a calendar
round trip and an interval-replaces-rule edit, so the fake and the fakeredis-backed adapter are
checked interchangeable on the new field.

No SQL and no proto changed, but the codec did, so two real-stack validations were run
(agent, 2026-07-14) rather than assumed. **Live Redis:** the contract suite's integration leg
passed against the containerized Redis, and was mutation-proven to actually exercise the new
key (encoding `rule` as `None` turns the *live* test red, not just the fakeredis one).
**The real brain image:** a scripted end-to-end run inside `cortex-brain:latest` against that
same Redis resolved `Europe/Bucharest` in-image, created "every weekday at 09:00" through the
real `ScheduleTaskTool`, read it back through `list_scheduled` as
`due 2026-07-22T09:00:00+03:00, every mon, tue, wed, thu, fri at 09:00`, fired it through a
real `build_ticker` ticker, and re-armed at `2026-07-23T09:00:00+03:00`: same wall-clock hour,
rule intact across the fire. Remaining behind the same shape:

- **Monthly, yearly, and day-of-month rules** ("the 1st of each month"). A new field on
  `CalendarRule` plus a wider candidate walk; the current walk is bounded to one week precisely
  because the day set is weekly.
- **Editing a rule in place.** `edit_scheduled` can replace a rule with an interval or stop it
  repeating, but cannot *set* or retime one; that needs `at_time`/`on_days` on the edit verb and
  a `ScheduleEdit` that carries the third case.
- **A per-rule timezone**, per the zone decision above.
- **Cron expressions**, if a rule this shape cannot express ever turns up.

## Addendum (2026-07-14): `edit_scheduled` authors and retimes a calendar rule

The calendar addendum shipped a rule the model could create but never change: `edit_scheduled`
could replace one with an interval or stop it repeating, and nothing more, so "move my 09:00
standup to 10:00" meant cancel-and-recreate. `at_time`/`on_days` join the edit verb, behind the
unchanged `ScheduleStore` port and with no codec or record change (the `rule` key already rides
the record). Decisions:

- **Setting a rule re-derives `due_at`; this is the one place the edit verb's "the next due
  time is never moved" rule bends.** It bends because a rule *is* its own grid. The calendar
  addendum made a calendar item's `due_at` an occurrence of its own rule by construction:
  creation derives it and every fire re-derives it through `next_occurrence`. An edit that set
  a new rule while pinning `due_at` would leave the item in a state neither creation nor firing
  can produce, its next fire at a wall time the rule does not name, and it would be plainly
  wrong to read: retiming a 09:00 standup on Tuesday afternoon would still fire at 09:00 on
  Wednesday. The **interval** case is deliberately not revisited. An interval's occurrences are
  `due_at + k*every`, anchored on `due_at`, so leaving it put is the definition of "future
  re-arms only"; a rule has no such anchor and derives its occurrences from the wall clock
  alone. The two shapes differ in the thing the original decision turned on.
- **The derivation happens at the tool boundary, not in the store.** `apply_edit` is pure and
  clockless and both stores share it, so handing it a `Clock` and a `DisplayZone` would push
  time policy into the adapters. Instead the rule and the first occurrence it implies are
  derived together at the verb (exactly as creation's `_parse_calendar` already does) and ride
  the edit as one frozen `RuleChange(rule, due_at)` value. Binding the two fields into one
  value is what keeps `due_at` from becoming the general "set the due time" knob this verb
  refused: there is no way to express a bare due-time move, only a rule whose occurrence it is.
  `EditScheduledTool` therefore gains the `Clock` and `DisplayZone` its snoozing sibling already
  takes.
- **A rule change re-arms the item exactly as `snooze` re-arms a fired reminder.** Naively
  moving `due_at` would have been a live defect, not a refinement, and the audit that found it
  is worth recording: a fired-but-undelivered reminder is `DONE` and sits on the deliverable
  index, and today `DONE` items are **never** on the due index (`finish` only re-adds a
  re-arming item). `ack` leans on that, deleting a `DONE` record with no `zrem` of the due
  index. A rule edit that merely `ZADD`ed the due index would therefore have put a `DONE` item
  back in the claim path, where `claim_one`'s staleness re-check (`PENDING and due_at > now`)
  does not stop it, and the fired one-shot would fire a second time. The fix needs no new
  concept, because `apply_snooze` already answers this exact situation: a rule change re-arms
  `PENDING` at the derived occurrence and clears `deliverable_since`, so a fired reminder fires
  fresh rather than re-delivering stale. It also clears `anchor`, which is interval-grid state a
  rule has no use for and which would otherwise linger as dead data on a previously-snoozed item.
- **`rule` and `set_every` are mutually exclusive on the edit, enforced in `__post_init__`.**
  The item's one-shape invariant is kept true at the boundary the way `_parse_when` keeps it
  true for creation, rather than re-checked inside `apply_edit`. Clearing a rule needs no third
  case: `every_seconds: 0` already sets `set_every` with `every=None`, and `apply_edit` already
  drops the rule alongside, so the sentinel keeps stopping whichever shape the item had.
- **One index write joins the fenced transition.** The edit addendum called `edit_item` "the
  lightest of the guarded writes, a bare watched `SET`", true only while `due_at` stayed put. The
  rule branch now also `ZADD`s the due index and `ZREM`s the deliverable one, which is precisely
  `snooze`'s write set, under the same WATCH fence and the same racing-cancel-answers-`False`
  contract. The non-rule branches are untouched and still write only the record.
- **The taint rule is per-verb, not per-field.** A rule change injects no text, but the editing
  turn's taint still ORs onto the item and a task still cannot be edited under taint. One rule
  for the verb is easier to reason about than a per-field taint policy, and marking more than
  strictly necessary is the fail-closed direction. The result renders the new due time in the
  display zone when a rule moved it (the `snooze` precedent), and still never echoes stored text.

Remaining behind the same shape: **monthly / yearly / day-of-month rules**, **a per-rule
timezone**, and **cron expressions**, all as the calendar addendum left them.

## Addendum (2026-07-14): monthly day-of-month rules

The calendar addendum's rule names a wall time and a set of **weekdays**, so its occurrence
search is bounded to one week and "remind me on the 1st of every month" is unexpressible: the
nearest a user can get is a 30 day interval, which is the drift the whole rule shape exists
to avoid (it walks off the calendar by a day or three every month, and by a month every year).
Day-of-month recurrence lands here, behind the unchanged `ScheduleStore` port, with no record
version bump and no migration. Decisions:

- **A day-selector union on the rule, not a second optional field beside `days`.**
  `CalendarRule(hour, minute, on: DaySelector)` where `DaySelector = Weekdays | MonthDays`, both
  frozen values in `schedule_calendar.py`, with `DAILY` (every weekday) the default. The
  cheaper-looking alternative was `month_days: frozenset[int] | None` sitting beside the
  existing `days`, and it was rejected because it makes the type state a falsehood: a monthly
  rule would carry `days == EVERY_DAY`, a field it ignores, and a reader cannot tell an authored
  weekly rule from a defaulted one. It also demotes "a rule has exactly one day selector" from a
  shape to a cross-field check in `__post_init__`. The union makes the invariant structural, and
  it is the seam a **yearly** rule joins as a third variant rather than as a fourth field
  widening the same invariant.
- **A day the month does not have clamps to that month's last day; it never skips the month.**
  `on_month_days: [31]` fires on 28 February (29 in a leap year) and on 30 April. The competing
  policy, skipping a month that lacks the day, was rejected on two counts. First, it is the same
  question daylight saving already asked and this ADR already answered: an occurrence in a
  spring-forward gap fires just past the gap, late but never skipped, so a calendar irregularity
  **moves** an occurrence here and does not delete one. Second, the failure modes are not
  symmetric. Skipping means a monthly reminder silently does not fire in up to five months of
  the year, and a reminder that never arrives is the worst outcome this feature has, while
  clamping fires it at the closest instant the month actually contains. One property falls out
  rather than being designed: `on_month_days: [31]` **is** how a maintainer says "the last day of
  every month", so no separate last-day selector is owed. Clamping can also collide (30 and 31
  both land on 28 February), and the walk works in resolved dates, so a collision fires once.
- **The walk stays total by the same construction the weekly one used, not by a cap.** Each
  selector answers `walk(start) -> (candidates, wrapped)`: the dates from `start` onward that
  its own window contains, plus one fallback that is unconditionally later than any instant
  whose local date is `start`. For `MonthDays` that fallback is the earliest clamped day of the
  **next** month, which is later by date and therefore later by instant in any zone, so
  `next_calendar_due` keeps one body, dispatches once, and terminates by construction with no
  defensive iteration cap and no unreachable branch to fake coverage over. A non-empty selector
  stays load bearing for exactly the reason the calendar addendum gave.
- **The model writes `on_month_days`, a list of integers, refused alongside `on_days`.** Not one
  polymorphic `on_days` accepting either weekday names or numbers: the two selectors mean
  different things and a small model asked to mix vocabularies in one field will, whereas two
  named fields with an explicit mutual-exclusion correction are self-teaching. Both creation
  (`schedule_task`) and the edit verb (`edit_scheduled`) take it, so a rule can be authored,
  retimed, and switched between weekly and monthly in place. The parsing of the model's day
  vocabulary moved to `schedule_day_args.py` at the 300 line cap, shared by both callers, which
  is the same responsibility line `schedule_verb_args.py` already draws.
- **The codec distinguishes the selectors by which key is present, not by a discriminator or a
  version bump.** A weekly rule still writes `days`, a monthly one writes `month_days`. Records
  written before this addendum decode as weekly (the additive-key precedent `anchor` and `rule`
  both set), and a weekly rule written after it is byte-identical to one written before, so the
  only records that change shape are the ones using the new capability.

Remaining behind the same shape: **yearly rules** (a `YearDays` variant naming a month alongside
its days, the union's designed third case), **a per-rule timezone**, and **cron expressions**,
all as the calendar addendum left them.

## Addendum (2026-07-14): yearly rules, the day-selector union's third variant

The weekly and monthly selectors bound their search to a week and to a month, so an annual
occurrence ("every 25 December", "renew the domain on 3 March") has no expression but a
365 day interval. That interval is worse here than anywhere else the rule shape has replaced
one: it drifts a full day every leap year and never self-corrects, so a birthday reminder walks
off its own date within a decade. `YearDays` lands as the third `DaySelector` variant the
monthly addendum designed the union for, behind the unchanged `ScheduleStore` port, with no
record version bump and no migration. Decisions:

- **A set of month-and-day pairs, not a month alongside a day set.** The monthly addendum
  predicted "a `YearDays` variant naming a month alongside its days", and implementing it
  corrected that: a single `month` field with a day set expresses "the 1st and 15th of March"
  but not "25 December and 1 January", which is the more common annual shape (holidays,
  renewals, and birthdays cluster across months, not within one). `YearDays` therefore holds
  `frozenset[MonthDay]`, `MonthDay(month, day)` being an ordered frozen pair whose natural sort
  **is** chronological-within-the-year, which the walk and the codec both lean on. The
  single-month form is the strictly weaker shape and is reachable anyway as pairs sharing a month.
- **February 29 clamps to February 28 in a common year, by inheritance rather than by a new
  decision.** This is the monthly addendum's clamp policy applied to the one date the year-long
  window makes irregular, and it is the same policy daylight saving already set: an irregularity
  **moves** an occurrence and never deletes one. Skipping would mean a 29 February reminder fires
  in one year of four, which is the silent-never-fires failure mode that policy exists to refuse.
  The clamp collapses `{02-29, 02-28}` to one fire in a common year and two in a leap year, the
  same collision the monthly `{30, 31}` case already resolves in resolved dates.
- **The walk stays total by the same `(candidates, wrapped)` construction.** `YearDays.walk`
  answers this year's clamped dates from `start` onward plus the **next** year's earliest, which
  is later by date and therefore later by instant in any zone. `next_calendar_due` keeps one
  body and no cap. The one new failure mode is real and already handled: a rule walking past
  `date.max` raises rather than looping, and `next_calendar_due` already answers `None` for an
  occurrence it could not persist, so the recurrence ends instead of re-arming an impossible fire.
  **Mutation testing corrected one belief about this contract**, and it applies to the existing
  monthly selector too: the `>= start` filter inside `walk` is an optimization, not the
  strictness guard. Removing it from either selector leaves the whole suite green, because an
  earlier date can only resolve to an earlier instant (a daylight-saving fold moves an
  occurrence by an hour, never across a day), so `next_calendar_due`'s `instant > after` is
  what actually enforces "strictly after". Both filters stay, for a locally true `walk`
  contract and fewer resolutions, but neither is claimed as a proven guard.
- **The model writes `on_dates`, a list of `MM-DD` strings, refused alongside either sibling.**
  Not `on_year_days`, despite the field-name symmetry with `on_days`/`on_month_days`, because
  "year day" already means the ordinal 1..366 (`tm_yday`) and a small model that reads it that
  way writes `[359]` for Christmas, which validates as nothing. `on_dates` names what the values
  are. A full ISO date (`2026-12-25`) is **refused rather than truncated**, matching `at_time`'s
  refusal of a seconds field or an offset: silently dropping the year would answer a different
  question than the model asked, and the correction teaches the format in one round trip. All
  three selectors stay mutually exclusive, refused at the parse boundary.
- **The codec writes `year_dates`, the third present-key variant.** Records predating this
  addendum decode as weekly or monthly exactly as before, and both existing variants still
  encode byte-identically, so the only records whose shape changes are the ones using the new
  capability. The pairs ride as two-element arrays, which is what `MonthDay`'s tuple-shaped
  sort already produces.
- **The three day-selector JSON-schema properties moved to `schedule_day_args.py`, beside the
  parser that reads them.** `schedule_tools.py` and `schedule_verbs.py` each advertised their own
  copy, so a third selector would have been a third divergence between two descriptions of one
  vocabulary; the line cap made that concrete by leaving the edit verb too little headroom to
  hold a third. The module that owns how a rule's dates are *written* now also owns how they are
  *advertised*, one definition for both verbs. `at_time` stays with each caller, because its
  meaning genuinely differs between them (an alternative to `at`/`in_seconds` on creation, a
  replacement for `every_seconds` on an edit).

Remaining behind the same shape: **a per-rule timezone** and **cron expressions**, as the
calendar addendum left them. The union is now closed over the three cycles a wall-clock rule
can name (week, month, year); a fourth variant would be a different kind of thing (an nth-weekday
rule, "the second Tuesday"), which is why it is not owed by symmetry.

## Addendum (2026-07-14): the Rust `BrainTransport` reminder methods

The body-side half of decision 5 lands, closing the first of the three items the
in-slice remainder named. `BrainTransport` grows `list_due_reminders()` and
`ack_reminder(reminder_id)` (plus the `DueReminder` core mirror), `BrainSeamClient`
translates both in a new `body/crates/rpc/src/reminders.rs`, and `RetryingTransport`
forwards them under the split below. The overlay surface and the body-side `Notify`
trait remain. Decisions:

- **`ack` stays unretried, and for a sharper reason than "it is a write."** The original
  decision noted that acking twice is harmless brain-side, which is true and is why the
  method is safe to expose at all. What it does not survive is a **lost reply**: the
  first attempt clears the reminder, the response never arrives, and the retry answers
  `acked=false` for a reminder this very call cleared. The caller then reads "there was
  nothing to ack" and cannot tell that apart from a stale dismissal. A surfaced transient
  error is the honest answer, and the pull path already recovers by construction, since
  the next overlay open re-lists whatever is still deliverable. So the split here is not
  idempotent-vs-not, it is *whether a repeat can change the answer*.
- **A `bool`, not a `Result<(), _>`.** `acked=false` is a state report (unknown id, or
  already acked), never a failure, so it stays in the `Ok` channel; only a transport or
  status failure is an `Err`. This mirrors the brain's own `ScheduleStore.ack`.
- **Nothing in the adapter special-cases the schedule-free brain.** `CORTEX_SCHEDULE_BACKEND=none`
  answers an empty list and `acked=false` at the brain (decision 5, deliberately not
  `UNAVAILABLE`), which is exactly what a brain with nothing due answers, so the body needs
  no mode of its own. Had the brain aborted instead, the body's own `is_transient`
  classifier would have turned every overlay open into a retry-backoff storm, which is the
  coupling that decision was protecting.
- **The reminder translation is its own module.** `client.rs` holds the connection
  lifecycle and the port impl; the row mapping lives beside the session reads' mapping
  (`sessions.rs`), which is the split the line cap already forced once and the reason
  neither file needed touching beyond four lines.

CI-gated at 100% line+region+branch over the existing loopback fake brain, and
mutation-proven: dropping the `list_due_reminders` retry, adding one to `ack_reminder`,
and corrupting the row mapping (taint read off the wrong flag) or the ack answer each turn
a distinct test red.

## Addendum (2026-07-14): the overlay's reminders-on-open surface

The second of the three items the in-slice remainder named, and the one that makes pull
delivery real: `ListDueReminders`/`AckReminder` now have a consumer. The `BrainBridge` port
grows `listDueReminders()` / `ackReminder(id)` (plus a `DueReminder` mirror of the wire row),
two thin Tauri commands in `src-tauri/src/reminders.rs` implement them over the resilient
transport, and the overlay fetches on open, renders a card stack above the history, and acks
what the user dismisses. Only the body-side `Notify` OS trait (push delivery) remains.
Decisions:

- **The fetch fires on the rising edge of visibility, not on mount and not per turn.**
  The body starts hidden in the tray and stays resident, so a mount-time fetch would deliver
  reminders to a window nobody is looking at, and the ack-on-dismiss contract would then be
  describing a card that was never seen. A latch on `mode !== "hidden"` that re-arms on hide
  gives exactly one read per summon, which is what "surfaced when the overlay next opens"
  (decision 5) says. Re-opening the panel from the orb mid-turn does not refetch, because the
  overlay never became hidden in between.
- **Dismissal is optimistic and a failed ack is never retried.** The card leaves the moment
  the user dismisses it and the ack rides the bridge unawaited, so a slow or unreachable brain
  cannot make the gesture feel stuck. If that ack is lost the reminder stays deliverable and
  the next open surfaces it again, which is the bias this slice already chose (a repeated
  reminder beats a lost one). This is also the layer that pays for the transport addendum's
  decision to leave `ack_reminder` unretried: the recovery is a re-read on the next open
  rather than a retry, so a lost reply can never be mistaken for a stale dismissal.
- **The list lives in the reducer, not in component state.** A dismissal has to survive
  re-renders and mode changes, and every branchy overlay decision is gated in `overlayState`
  by construction (ADR-0011). Two actions cover it: `remindersLoaded` replaces the list
  wholesale (the brain is the authority on each open) and `reminderDismissed` filters one id
  out. Both are total: an unknown id is a no-op, so a double-click cannot corrupt the list.
- **The pull loop is its own hook.** `useReminders(bridge, mode, dispatch)` owns the latch and
  the ack; `useOverlay` composes it and re-exports `dismissReminder` on the controller. The
  responsibility line is the same one `sessionState.ts` drew: `useOverlay` owns the turn and
  the chat list, this owns the delivery loop, and the line cap was going to force the split at
  the next overlay feature regardless.
- **Reminder text is rendered inert, and deliberately never linkified.** It is a plain text
  node with an `untrusted source` badge when `tainted` is set (the wire bit exists for exactly
  this, decision 5); the browser pass corrected the badge's own treatment, since a dashed
  neutral pill (the first attempt, reasoning that a provenance mark is not a working affordance
  and so may not touch the accent) turned out to read as just another pill beside `repeats`. It
  now also carries the error bubble's tint at a lower alpha, which is the one non-accent
  "wait to be seen" colour the design already has, and keeps the dashed border so the signal
  does not rest on hue alone. The badge is not decoration: reminder text is the one string the overlay
  displays that **never passes the ADR-0015 output guardrail**, because it is not reply text and
  never streams through an `OutputFilter`. A URL inside it has therefore had no redaction pass,
  which is why nothing in the card may ever become a clickable link. The overlay renders no
  markup anywhere today, so this costs no code; it is written down because the invariant is
  invisible in the diff that would break it.
- **A recurring reminder says so on its card.** Acking clears this occurrence and the series
  re-arms (decision 2), so a card that looked identical to a one-shot would make dismissal read
  as cancellation. The word `repeats` is the whole fix; cancelling a series stays a conversation
  with the cortex (`cancel_scheduled`), never a button here, since this surface is delivery and
  has no gated-write path.
- **A failed list leaves the previous cards in place**, matching the chat list's rule exactly:
  a transient brain outage should not silently empty a surface that says "you have things
  waiting". The resilient transport (ADR-0024) has already retried the read with backoff by the
  time this `.catch` runs.

CI-gated at 100% over the fake bridge (fetch-on-open latch including the re-arm and the
no-refetch-from-orb case, load failure, optimistic dismissal, failed ack, unknown-id no-op,
taint badge, recurring hint, empty state), with ten guards mutation-proven. **Browser-validated
2026-07-14** in headless Chromium against the demo bridge, both themes: the summon renders the
stack, dismissing one card removes exactly it, a hide-and-re-summon re-pulls without the acked
one (the latch and the ack round trip end to end), the cards contain **zero anchors** (the
inert-text invariant, asserted in the live DOM rather than only in jsdom), and an eleven-card
probe confirmed the stack scrolls itself at its `30vh` cap instead of pushing the composer out
of the panel. The Tauri command pair is the ungated host glue (the `sessions.rs` precedent),
type-checked on Linux but validated on Windows; the real hotkey to overlay path stays
Host-Windows.

## Addendum (2026-07-14): the reminder card's origin chat

A reminder arrives with none of the conversation that asked for it, so `Stand-up in 10
minutes` is delivered without the thread where the standing meeting was being discussed.
`session_id` has ridden every `DueReminder` since decision 5 and the overlay already loads a
chat on demand, so the card now offers to open the one it came from. Overlay-only: no proto
field, no transport method, no reducer action, no brain change. Decisions:

- **The control is a sibling of the reminder text, never the text itself.** Making the card
  body clickable was the obvious shape (the switcher's rows are exactly that) and is the one
  thing this surface may not do. Reminder text is the string no output guardrail inspected,
  so an attacker who lands a reminder writes the label on any control it becomes, and `Click
  here to verify your account` as a real, working button teaches the habit that the inert-text
  invariant exists to prevent. A separate control with a fixed app-authored label keeps the
  clickable thing app chrome; what a stranger wrote stays a text node.
- **Opening is not acking.** The two gestures stay separate because their failure modes are
  not symmetric: an ack destroys the reminder and navigation does not, so a mis-click on the
  way to the context may not silently clear what it came to explain. The card stays until it
  is dismissed, which also lets the maintainer read the thread and *then* decide.
- **No control when there is nothing to go to, or nowhere to go.** A session-less caller
  sends `""` (the ticker's own fires, decision 5), and a card whose origin is the chat already
  on screen would offer a navigation that changes nothing while *cancelling the turn running
  in it*, since opening a chat abandons the current one exactly as the switcher does. Both are
  rendered absent rather than disabled: a disabled control invites an explanation, and there
  is none worth giving.
- **It reuses the switcher's own handler.** `Panel` already receives `onSelectSession`
  (`useOverlay.openSession`), so the card passes through it unchanged and no new prop crosses
  `Overlay` → `Panel`. One chat-loading path, one set of semantics (deny a pending confirm,
  cancel the stream, hydrate from the store), and a reminder cannot drift from the switcher.

CI-gated at 100% with four guards mutation-proven (the empty-session check, the current-chat
check, the id it opens with, and an ack folded into the open handler; each reverted
individually turns a distinct test red). **Browser-validated 2026-07-14** in headless
Chromium against the demo bridge, both themes: three cards render two controls, since the
cold-start-adopted chat's own card correctly offers none; clicking one loads that chat
(title and history both swap) while the stack keeps all three cards, proving open does not
ack; and the freshly-current chat's remaining cards drop their controls in the same render.
The pass also settled the resting treatment, which is the same correction the badge needed:
at the meta row's own `--dim` the label read as a third piece of metadata, so it rests one
step brighter (`--muted`) and grows the switcher's panel-tinted pill on hover. An action
nobody can see before hovering it is not an action.

## Addendum (2026-07-15): a per-rule timezone for calendar recurrence

The calendar addendum shipped a rule whose wall time means the one zone
`CORTEX_SCHEDULE_TZ` names, and recorded the per-rule zone as "the additive extension if a
second zone ever exists: a new field on the same value, not a different shape". It lands here.
The want is concrete for an assistant that travels: "remind me at 09:00 New York time" while
the deployment renders Bucharest, or scheduling around a trip without moving every other
reminder. A rule can now carry its own IANA zone; omitting one keeps the deployment default,
so a zone-less rule is byte-for-byte what it was and still follows `CORTEX_SCHEDULE_TZ` (the
"your 09:00 follows you" reading the calendar addendum chose). Decisions:

- **The rule carries a resolved `DisplayZone`, and the record persists its name.** `CalendarRule`
  gains `zone: DisplayZone | None = None` as its last field. In memory the rule holds the same
  `DisplayZone` value the composition root already builds (an abstract `tzinfo`, so the core
  stays `zoneinfo`-free), and everything downstream reads it for free: `next_calendar_due`
  resolves each candidate against `rule.zone` when set and the passed deployment zone otherwise,
  the renderers show a per-zone item in its own zone, and the ticker needs no change because it
  reads the decoded rule. Only the IANA *name* is durable, encoded as an additive `zone` key
  inside the existing `rule` object; a zone-less rule writes no key and so encodes exactly as
  before, no version bump and no migration, the `anchor`/`rule` precedent again.
- **A `ZoneResolver` seam, injected only where a rule is built from a name.** A per-rule zone is
  an *open* set, so unlike the single deployment zone it cannot be pre-resolved once at boot: a
  name reaches the system only as model input (creation, edit) or as a stored record (decode),
  and each is where a name becomes a `DisplayZone`. The core defines a `ZoneResolver` (one
  method, `resolve(name) -> DisplayZone | None`) and a `UTC_ONLY_RESOLVER` default that knows
  only `UTC`, since resolving any other key reads the tz database, the impure edge step the core
  never takes. `parse_schedule`/`parse_edit` and the two rendering tools take the resolver the
  way they already take the deployment zone; the composition root injects the real,
  `zoneinfo`-backed one.
- **The codec self-resolves on decode; the store is untouched.** `decode` reconstructs
  `rule.zone` from the stored name through a `zoneinfo`-backed resolver that lives in the session
  adapter (deserialization of a durable value is adapter work, the same class as
  `config_schedule` turning the env key into the deployment zone). This deliberately keeps the
  resolver *out* of `RedisScheduleStore`: threading it through the store's constructor and its
  five `decode` call sites would have pushed `schedules.py` past the 300-line cap for a value the
  codec can supply itself, and the codec is exactly where a stored field becomes a typed value.
  The resolver is a default parameter, so no `decode` caller changed.
- **An unresolvable stored zone is a corrupt record, not a silent fallback.** Creation and edit
  validate the zone (an unknown key returns a correction the model reads back), so a name is
  never *stored* unresolvable; the only way a decode sees one is the tz database changing under a
  durable record. Decode then fails loudly, naming the key and the zone, exactly as it does for
  any other corrupt field, because the alternative (substituting the deployment zone) would fire
  the rule at a wall time nobody asked for, the silent-wrong outcome the codec's whole policy
  refuses. It is not attacker-reachable: the value is an IANA key the user's model wrote and the
  boundary already accepted.
- **A per-zone item renders in its own zone.** A rule that says "09:00 America/New_York" must
  show `due 09:00-04:00`, not the same instant printed as `16:00+03:00` in the deployment zone,
  or the confirmation and the listing would contradict the wall time the rule names. So the
  creation confirmation, the listing line, and the edit result render a calendar item's `due_at`
  in `rule.zone` when it has one and the deployment zone otherwise, and `CalendarRule.describe`
  appends the zone name (`every day at 09:00 (America/New_York)`) so a listing states the zone a
  bare wall time would leave ambiguous. Everything without a per-rule zone renders exactly as
  before.
- **`in_zone` is the model's vocabulary, valid only with `at_time`.** Both `schedule_task` and
  `edit_scheduled` gain an optional `in_zone` (an IANA key like `America/New_York`), parsed by
  the shared calendar-rule vocabulary in `schedule_day_args.py` so the two verbs cannot drift,
  the `at_time`/day-selector precedent. It is meaningful only with `at_time` (an interval has no
  wall clock to place in a zone) and refused otherwise with a message naming the reason, and an
  unknown key is a correction rather than a giant enum on the spec, since the IANA set is large
  and the resolver is the authority. Omitting it means the deployment zone, so the common single
  zone case writes nothing new.

CI-gated at 100% over the fakes and a `zoneinfo`-backed decode: the rule's zone-aware occurrence
math against a real `ZoneInfo` (a rule in a zone the deployment does not use fires at its own
wall time), `describe` naming the zone, the `in_zone` parse matrix on both verbs (resolved,
unknown, without `at_time`), the two specs advertising it, the renderers picking the rule's zone,
and the codec round-tripping the name plus failing loudly on an unresolvable stored zone and
decoding a pre-addendum record (no `zone` key) as zone-less. The default path (no `in_zone`, no
`zone` key) keeps its existing assertions unchanged, the regression check that the field is
additive. Remaining: **cron expressions**, as every calendar addendum left them; the per-rule
zone this entry closes needed a new field, never a new shape.

## Addendum (2026-07-16): the body-side `Notify` OS trait and the native toast

The last of the three in-slice remainders, so push delivery now exists end to end: the ticker's
`BodyGateway.notify` call reaches a real handler instead of the shape-now `Unimplemented`. The
port is `body_core::os::notify` (its own submodule, since `os.rs` sat at the line cap):
`Notify::show(&Notification) -> Result<bool, NotifyError>`, `Send + Sync` like `AudioControl`
because the server holds it across async tasks, with `Linux`/`MacosNotify` stubs behind the
coverage escape hatch and the real `WindowsNotify` (a `ToastGeneric` WinRT toast) in
`os_windows`. `body_rpc`'s `BodyService` server takes the second backend generic decision 6
predicted. Decisions:

- **Three corrections to decision 6's own framing, each found by reading the code.** (1) It
  placed the Windows implementation in the **Tauri shell**; it lands in `os_windows` instead,
  beside `WindowsHotkey` and `WindowsAudioControl`, because that crate already *is* the
  per-platform backend home, is already `cfg(windows)` (so CI never builds or measures it), and
  the shell's own module doc commits it to holding no branchy decision. The shell keeps exactly
  what it kept for volume: which backend to construct, and from which env var. (2) The server
  type could not stay `VolumeService`, since it now answers two unrelated OS capabilities; it is
  `OsService<A: AudioControl, N: Notify>` (an `OsService::new` + `body_service(audio, notifier,
  token)` rename, no behavior change, ADR-0023's text left as the record of what it was then).
  (3) The `unsafe` authorization ADR-0023 scoped to Core Audio had to widen by one line: WinRT
  projections are safe, but activating a WinRT factory needs a COM-initialized thread and the
  server runs on tokio workers that have none, so the toast module makes the same idempotent
  `CoInitializeEx` call the audio backend does. Still COM only, still `os_windows` only.
- **The inert-text rule is a property of the value, applied at construction.** Decision 6 phrased
  it as an instruction to the Windows implementation ("must render `title`/`body` as inert
  escaped text"), which would have left the seam's data-not-instructions posture resting entirely
  on the one file no gate ever sees. `Notification::new` therefore replaces every control
  character with a space and bounds each line at 200 characters, in the pure core, at 100%. A
  fired reminder is the one string the body renders that **no output guardrail inspected**
  (ADR-0015 filters streamed replies, not store rows), so the guarantee has to hold for every
  backend that will ever exist, not for the one that exists now.
- **Escaping is the renderer's step, not the value's, and it still lives in the core.** These
  pull apart on inspection: a toast template is XML, so `&` must become `&amp;` there, while a
  future Linux backend would render through a markup-limited notification body where a
  pre-escaped string displays the entity literally, and a backend that does its own escaping
  would double-escape. So `Notification` carries plain inert text and `os::escape_xml` sits
  beside it as a gated helper the XML-templating backend calls. Both halves are covered on Linux;
  what remains untested here is only the call sequence into the OS.
- **A control character is replaced, never dropped, and long text is truncated, never refused.**
  Dropping fuses two words across a stripped newline; truncation with a trailing ellipsis keeps
  the reminder rather than losing it to a payload the OS rejects whole. Both follow the bias this
  slice has taken everywhere else, that an irregularity degrades an occurrence and never deletes
  one (the daylight-saving fold, the month-length clamp, the leap-day clamp).
- **`shown=false` is a state report, and the toast backend can actually produce one.** The wire
  field would otherwise have been dead: a WinRT `Show` either succeeds or throws. But
  `ToastNotifier.Setting` answers *before* showing whether notifications are switched off for
  this app, this user, or by policy, which is a genuine "the host was reached and declined". That
  answers `Ok(false)`, an error answers `Err`, and the brain treats both identically (the
  reminder stays deliverable and the pull path shows it on the next open), so the split changes
  nothing but the honesty of the body's own logs. `NotifyError` splits `Unavailable`/`Backend`
  onto `Unavailable`/`Internal` exactly as `audio_error_to_status` does.
- **The taint badge is body-authored, fixed text.** A tainted reminder renders one extra
  attribution line reading `from an untrusted source`, decided in the core by
  `Notification::attribution()`. It is a constant rather than anything derived from the reminder,
  for the reason the overlay's card already learned: an attacker who lands a reminder writes the
  text, so they may never write the label that describes it.
- **The app identity is config, because an unpackaged app cannot invent one.** Windows attributes
  a toast to an `AppUserModelID` that must be carried by an installed Start Menu shortcut, so
  `WindowsNotify::new(app_id)` takes it and the shell reads `CORTEX_TOAST_APP_ID` (default
  `dev.cortex.body`, the Tauri identifier). A `tauri dev` run has no such shortcut and can borrow
  a registered identity through the same variable (runbook `docs/runbooks/scheduling.md`).

CI-gated at 100% line+region+branch: the core's inert-text rule (control characters in both
lines, the exact bound, the ellipsis past it, non-ASCII text kept whole), the attribution on both
taint values, `escape_xml` over all five entities plus pass-through, the port through a generic
bound over a fake (shown, declined, failed), and four new loopback contract tests on the real
`BodyService` server proving the wire values reach the backend already inert and badged, that a
declined toast answers `shown=false` rather than a status, and both error arms. **Mutation-proven**
across nine reverted guards, each turning a test red: dropping the control-character
replacement, the length bound, and the truncation mark; making every notification claim untrusted
provenance; dropping the ampersand escape; reporting a declined toast as shown; mapping an
unreachable notification service to `Internal`; and swapping title for body or dropping the taint
bit on the way into the value. The two truncation mutations land on one test, as do the two
mapping ones, which is recorded rather than papered over. Beyond the gate,
`os_windows` and the Tauri shell were both type-checked and clippy-checked against the real
`windows` crate for the `x86_64-pc-windows-msvc` target from Linux, which is a compile check and
nothing more.

**Host-Windows (host-only), unchanged from what this slice always owed:** whether a real toast
appears, reads well, and renders a hostile reminder inertly. Fire a reminder with the body
running and the brain wired (`CORTEX_BODY_BACKEND=grpc`); the toast should carry the text, badge
an untrusted one, and the reminder should *not* still be waiting in the overlay afterwards, since
a shown toast is delivery and the ticker acks it.

**Deferred here, recorded in [docs/refinements/scheduling.md](../refinements/scheduling.md):**
**toast activation** (clicking a toast does nothing today; routing it to summon the overlay on
the origin chat needs an activation channel from the shell into the running app, and for an
unpackaged app a registered COM activator, which is a larger piece of Windows plumbing than the
delivery it would improve). The two deferrals that were blocked on this half, **task-outcome
delivery as a notification** and a **push retry policy** beyond next-poll-pull, are now
unblocked and stay deferred on their own merits.

## Addendum (2026-07-16): the tainted-reminder badge deferral closes as satisfied

The Consequences list above defers "overlay badge/UX polish for tainted reminders", written when
no overlay reminder surface existed and therefore naming a badge nobody had built yet. The
overlay addendum built it, and its browser pass then corrected the badge's own treatment, so the
polish this deferral asks for was paid inside the slice that created the thing to polish. Read
against the tree today it is **satisfied, and closes with no code change**; the outcome is
recorded in [docs/refinements/scheduling.md](../refinements/scheduling.md). What was checked:

- **The wire bit is consumed, not merely carried.** `DueReminder.tainted` (decision 5) reaches
  `Reminders.tsx` through the transport, the Tauri command, the bridge mirror, and the reducer,
  and a `tainted` row renders an `untrusted source` tag in the card's meta row while a plain row
  renders none. The label is fixed app chrome; nothing in it derives from the reminder, which is
  the same rule the toast's attribution states body-side.
- **The badge is distinguishable from the neutral tag beside it.** `repeats` and the taint mark
  would otherwise be two pills of one weight. The badge carries the error bubble's tint at a
  lower alpha and keeps a dashed border, so it separates from `repeats` and the separation
  survives without hue. That treatment is the browser pass's own correction, not a first guess.
- **Reminder text stays inert.** Every field is a plain text node and the card linkifies nothing,
  which matters because a fired reminder is the one string the overlay shows that no ADR-0015
  output guardrail inspected. A hostile-text test asserts the card holds no anchor element, and
  the origin-chat control is a sibling of the text with an app-authored label, so what a stranger
  wrote never becomes the label on a working affordance.
- **Neither same-day landing reopens it.** The native toast badges a tainted reminder with its
  own fixed attribution line, so push delivery is not an unbadged path around the badged card.
  ADR-0027's structured provenance widened the *turn* stamp only: `ScheduledItem` stores the
  taint bit with no sources and `DueReminder` has no source field, so a card cannot yet name
  *which* source tainted it. Displaying that is the separately recorded deferral on provenance
  across the stores, and is a store plus proto change rather than badge polish.

Reopening this needs a named defect in the rendered card. The likeliest source is the user's
Windows pass on the real overlay, which stays owed and is the one look no gate reaches.

## Addendum (2026-07-16): the occurrence-history table declined, no consumer reads a fired occurrence

The Deferrals list above carries "occurrence history (coalesced single-slot deliverability keeps no
per-fire records, and terminal cleanup deletes a one-shot task's outcome with the record)", and the
Risks list ties unseen-toast recovery to it ("a toast shown while the user is away still acks ...
unseen-toast recovery (history) is the deferred occurrence-history item"). Read against the tree
today it is **declined, with no code change**; the outcome is recorded in
[docs/refinements/scheduling.md](../refinements/scheduling.md), and the deferral moves to the
backlog's dead-until-a-consumer list. What was checked:

- **The store keeps no per-fire record, exactly as the entry said, confirmed live.** A fired
  reminder sets the single `deliverable_since` slot, which `ack` clears and a re-fire overwrites
  (coalesced, one slot); a task overwrites the single `last_outcome`; a terminal one-shot is deleted
  at `finish` (`next_due=None`, not deliverable) with its outcome; and a one-shot reminder the body
  reports `shown` is `ack`ed by the ticker at once, so `RedisScheduleStore.ack` deletes its DONE
  record. A pass against the compose Redis showed each: after a one-shot fired and was acked no
  `cortex:*` key remained, a recurring item survived the fire with `deliverable_since`/`last_outcome`
  both back to `None` (no trace it had fired), and a one-shot task's outcome vanished with its
  record. The unseen-toast gap is therefore real: a one-shot reminder firing to an empty room is
  delivered by a toast nobody saw and then vanishes, and the next overlay open reads nothing back.
- **Nothing reads a fired occurrence.** The seam exposes only `ListDueReminders`, which maps the
  `deliverable()` awaiting-ack slot, and `AckReminder` ([proto/body.proto](../../proto/body.proto)).
  `Reminders.tsx` renders that slot, and acking removes a row by contract, so it cannot double as a
  history view without breaking the ack it is. `list_scheduled` reads `last_outcome`, but only the
  single last line of a still-active item, never a history. A "recently fired"/"you missed these"
  recovery surface, the entry's own consumer, does not exist.
- **Building it is a full stack the reader does not yet justify.** A durable occurrence log needs a
  new store read the in-memory fake must also answer, a growth or retention policy on an otherwise
  unbounded write-only key, a new `BrainService` RPC, a `BrainTransport`/`BrainBridge` method with
  its Rust and Tauri adapters, and a new overlay component. This ADR's own "Per-occurrence delivery
  records" rejection turned on the same point ("a second entity and a growth policy, to preserve
  duplicate fires nobody reads at personal scale"), so shipping the record now would ship the growth
  policy it warned against with nothing to shape it. A real durable history wants queries and
  retention, which is the deferred Postgres durable twin rather than the Redis this would grow
  unbounded, so the two reopen together.

Reopening this needs a surface that reads a fired occurrence (a recovery view, or an audit sink for
what fired). It is then the record and that surface designed as one piece, arriving as a store read
plus a seam RPC rather than a log built ahead of its reader.

## Addendum (2026-07-16): task-outcome delivery, and the push retry policy sharpened

The two deferrals this ADR listed as "task-outcome delivery as a notification" and "a push retry
policy beyond next-poll-pull" came due once the `Notify` backend landed. They decomposed into one
thing to build and one to sharpen.

- **What a finished task delivered before.** The ticker's `_fire_task` finished with
  `deliverable=False`, so a task's result went only to the single `last_outcome` slot, read by
  nothing but `list_scheduled`; a one-shot task was deleted at `finish` (terminal cleanup), taking
  its outcome with it. Nothing proactively told the user a scheduled task had run, and its result
  could vanish before anyone saw it. That was the one-shot-task half of the occurrence-history gap.

- **Task-outcome delivery landed by reusing the reminder ladder.** The reminder path already
  finishes `deliverable=True` and pushes over `BodyGateway.notify`, acking on a shown toast and
  staying deliverable for pull otherwise, and the deliverable/ack machinery is **kind-agnostic** end
  to end (`ScheduleStore.deliverable()` and the Redis `DELIVERABLE_KEY` index filter nothing by
  kind; `list_due_reminders`/`Reminders.tsx` render whatever the store yields). So `_fire_task` now
  finishes `deliverable=True` and delivers through the same shared `_deliver` helper (renamed from
  `_push`, generalized to a title and body), pushing the **outcome** (never the standing
  instruction) under a `TASK_TITLE` toast, and `reminder_to_proto` maps a task's `last_outcome` onto
  `DueReminder.text` so the pull recovery shows the result. This needed **no store, proto, or
  overlay change**. A one-shot task's outcome now survives its fire (DONE-while-deliverable until
  acked), closing the one-shot-task half of the occurrence-history gap. The reuse leaves a task
  outcome undistinguished from a reminder on the shared pull card (`DueReminder` has no `kind`),
  recorded as its own deferral.

- **Double-delivery is barred by the same ack, not a resend timer.** A shown push acks (pull will
  not re-show), a failed or declined push stays deliverable (pull shows once, dismissal acks), so
  exactly one of push and pull ever clears the deliverable slot. Mutation-proven: dropping the task
  delivery reddens the delivery tests, dropping the ack reddens the acked-not-deliverable tests, and
  dropping the outcome mapping reddens the pull test. Validated live against the compose Redis (a
  one-shot task fired, pushed, acked, and left no `cortex:*` key; a body-down fire left the outcome
  on the deliverable index for pull).

- **The push retry policy is deferred, sharpened, and moved to fix-when-it-bites.** The safe retry
  today *is* the deliverable-until-acked pull; a proactive re-push beyond it double-delivers.
  `NotifyRequest.reminder_id` is the item id, stable across a recurring item's re-fires, so the body
  cannot tell a retry of fire N from the legitimate fire N+1, and the `BodyGatewayError` a down body
  raises is indistinguishable from a shown-toast-with-a-lost-reply (the lost-reply idempotency hole
  the ack-retry split already turned on). A genuinely-safe re-push needs a **per-fire delivery id**
  the body dedups on, which is exactly the per-occurrence record the occurrence-history entry
  declined for want of a consumer, so the two reopen together. The trigger: a body that reconnects
  between a failed push and the next overlay open often enough that an outcome stuck-until-open is a
  real gap.

CI-gated at 100% line+branch over the fakes (the task fire delivering the outcome, the shown-push
ack, the body-down deliverable recovery, the no-body deliverable, the tainted-outcome toast badge,
the fenced-off no-delivery, and the pull mapping of a task outcome plus its instruction fallback).
Host-Windows validation is unchanged from what the `Notify` backend already owed: whether a real
toast appears and reads well.
