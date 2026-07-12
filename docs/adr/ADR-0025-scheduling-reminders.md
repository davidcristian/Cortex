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
  clock arithmetic is demanded of the model); the bounds mirror creation (the 60 s floor
  and ten-year ceiling, `parse_for_seconds` beside the creation parser). The tool reads the
  item first for a precise correction (unknown / recurring / firing now), then relies on
  the fenced transition for the race-free answer, so the read is advisory and the store is
  authoritative. No taint gate, matching `cancel_scheduled`: postponing an existing
  human-visible item is the same trust class as deleting it, and results never echo stored
  text.

CI-gated through the shared contract suite (fake + fakeredis interchangeably) and the tool
tests over the fake; the live Redis integration suite exercises the same contract on the
real backend (run 2026-07-12 by the agent against the compose Redis, passing).

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
