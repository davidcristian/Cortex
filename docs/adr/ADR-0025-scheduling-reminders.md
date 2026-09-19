# ADR-0025: Scheduling and proactive reminders

**Status:** Accepted (2026-09-19)

## Context

The assistant needs a sense of time: "remind me at 18:00 to stretch", "every weekday at 09:00
summarize my inbox". A schedule is created now and runs later on the brain's own initiative, either
as an autonomous **task** run through a subagent or as a **reminder** shown to the user. A reminder
is fetched when the overlay next opens, and is also sent over the brain to body direction of the
gRPC interface (ADR-0023).

- **The one hard rule applies.** A schedule outlives every model swap and brain restart, so every
  `ScheduledItem` lives in the external store, and a run is a stateless read, act, store pass.
  Nothing lives in the orchestrator beyond the run in progress.
- **Redis is already durable enough.** The base compose file runs Redis append-only on a named
  volume, and sessions, the state the hard rule exists to protect, already live there.
- **The mechanisms have precedents**: the dispatcher's taint stamp on stored work (ADR-0018),
  audited built-in tools (ADR-0010), the injected `Clock`, unary read RPCs (ADR-0021).
- **`Scheduler` is taken.** It means resource admission here (`SubagentScheduler`,
  `ResourceBudgetScheduler`, `scheduler.py`), so the time-based code is `ScheduleTicker` and
  `schedule*.py` throughout.
- **An autonomous run has nobody to ask.** It runs outside any turn, with no stream and no
  `Confirmer`, so its safety comes from what that path cannot reach and what it can be told to do,
  not from a confirmation.

## Decision

### 1. Durable schedules behind a fenced `ScheduleStore` port

`cortex_core/schedule.py` holds frozen values: `ScheduledItem` (`id`, `kind` reminder or task,
`text`, origin `session_id`, tz-aware `due_at` and `created_at`, recurrence as `every` or `rule`,
`anchor`, roster hint `model` with `""` for the default entry, `tainted`, `status` PENDING, FIRING
or DONE, `deliverable_since`, `last_outcome`), `ScheduleClaim(item, token)` and `FireOutcome`. There
is no CANCELLED status, because cancel deletes. The port (`ports_stores.py`) has eleven methods:
`add`, `get`, `list_active`, `cancel`, `snooze`, `edit`, `claim_due`, `finish`, `release`,
`deliverable`, `ack`. Every transition is guarded:

- **`claim_due`** takes items due at `now` plus FIRING items whose lease expired, oldest due first
  across both, at most `limit`, each under a fresh fencing token. Running is at-least-once: a lost
  reminder is worse than a repeated one. A record that fails to decode on this path is
  **quarantined** to a dead-letter key and logged, and the pass continues.
- **`finish(claim, outcome)`** applies only while the item is FIRING under that token and returns
  `False` for a stale claimant, so a run that outlived its lease cannot overwrite the new claim. It
  ORs the run's taint onto the item, then sets the item back to PENDING at the next due time or to
  DONE, and a DONE item is deleted at once unless it is deliverable.
- **`cancel` is permanent**: it deletes the item in any state, so a later `finish` finds no claim.
- **`release`** returns a FIRING item to PENDING with `due_at` unchanged, so a graceful shutdown
  strands nothing for a whole lease.
- **`ack(item_id, *, fired_at)`** clears the deliverable slot only while it holds that run (decision
  5) and deletes a DONE one-shot.

The Redis adapter runs each guard and its write in one WATCH, MULTI, EXEC transaction, and a raced
EXEC is treated like a stale token. The claim path re-checks the watched read and skips a PENDING
record whose `due_at` has moved into the future since the index snapshot, so a snooze or a
rescheduling committed in that window is not overridden. `InMemoryScheduleStore`
(`fakes_schedule.py`) and the Redis adapter pass one shared contract suite (`schedule_contract.py`),
races included; quarantine is tested on the adapter.

### 2. Recurrence has two forms, an interval and a calendar rule

An item has either `every` (a positive `timedelta`) or a `CalendarRule`, a wall time on chosen days
([ADR-0065](ADR-0065-wall-clock-schedule-times.md)), never both, which `__post_init__` enforces.
`next_occurrence(item, now, zone)` is the one entry point the ticker calls. For an interval,
`next_due` returns the first anchored occurrence strictly after `now` from `recurrence_base(item)`
(`anchor` when set, else `due_at`), so runs missed while the brain was down collapse into the one
that just happened. An occurrence past `datetime.max` ends the recurrence rather than raising.
Wall-clock time reaches the core only through `Clock`.

### 3. Five cortex-only built-ins through the audited dispatcher

`schedule_task`, `list_scheduled`, `cancel_scheduled`, `snooze_scheduled` and `edit_scheduled` are
built-ins, so subagents never see them (ADR-0010) and cannot re-schedule themselves.

- **The specification tells the model the time.** `schedule_task`'s description is rebuilt on every
  `describe_tools` walk and includes the current time in the display zone (ADR-0065 decision 1); no
  other context line tells the model the date.
- **Arguments.** `kind`, `text`, and exactly one of `at` (ISO-8601), `in_seconds` or `at_time` (a
  calendar rule, ADR-0065 decision 2); `every_seconds` between 60 s and ten years; `model` for a
  task. Bad arguments return `is_error` results and never raise. Ids are uuid4 from an injectable
  factory.
- **Creation bounds.** Active items are capped (`CORTEX_SCHEDULE_MAX_ACTIVE`, 32), and **a tainted
  turn cannot create a task**. A reminder only ever reaches a human, while a task instruction
  written by injected content would be a permanent directive fed to a subagent.
- **Trust.** Creation, cancel, snooze and edit results are `TRUSTED` and never echo stored text.
  `list_scheduled` echoes text and is `TRUSTED` only when every listed item is clean. The item's
  `session_id` comes from the dispatcher's `TurnStamp` and is never rendered.
- **Accurate advertisement.** `kind: "task"` and `model` are offered only when the spawn tool is
  configured. None of the five needs confirmation by default, and `CORTEX_TOOLS_GATED` can require
  it for any of them by name.

### 4. The `ScheduleTicker` is a stateless poll loop in the orchestrator

`run_from_env` starts the ticker beside `serve()` and cancels it on the way out; a done-callback
logs an unexpected exit. Every `CORTEX_SCHEDULE_POLL_S` it claims items, runs the batch concurrently
and finishes each claim. Each run is bounded by `wait_for(lease)`, and a hung run is cancelled and
released. A pass is wrapped in a logged catch-all, so a bug skips a pass rather than killing the
loop, and on cancellation it releases unfinished claims.

- **A reminder** finishes deliverable, then is sent (decision 6).
- **A task** is a synthetic `spawn_subagents` call through the ticker's own `ToolDispatcher` (the
  spawn tool alone, `LoggingAuditSink`, `confirmer=None`, the `CORTEX_TOOLS_GATED` set), stamped
  with the item's `session_id` and taint. That gives the run an audit line, the taint stamp that
  routes it to the injection-resistant model (ADR-0017), admission and the fail-closed confirmation
  check, with no change to `build_subagents`. The result's trust becomes the run's taint. With no
  spawn tool configured, the run finishes with an `ok=False` outcome saying so.
- **Safety comes from the structure.** The run has no confirmer, so tools that need confirmation are
  denied outright, and subagents hold only tools that need none, so no scheduled item reaches
  `send_email`.
- **Errors.** `ScheduleStoreError` skips the pass; `BodyGatewayError` leaves the item deliverable; a
  task failure is an `ok=False` outcome.

### 5. Fetched delivery, and an ack that identifies the run

`BrainService` has `ListDueReminders` (all sessions, each row with `session_id`, `tainted`,
`recurring` and `fired_at_unix_ms`) and `AckReminder` ([proto/body.proto](../../proto/body.proto)).
A store failure aborts with `UNAVAILABLE`. **With no store configured
(`CORTEX_SCHEDULE_BACKEND=none`) the list is empty and every ack returns `acked=false`**, never
`UNAVAILABLE`, which the body's retry would treat as transient on every overlay open.

**An ack identifies the run it showed.** A card can stay on screen for run N after run N+1 has
replaced the slot, and acking by item alone cleared N+1 unseen. `AckReminderRequest` includes the
card's own `fired_at_unix_ms`, and both stores clear the slot through the pure `acks_fire`
(`schedule_transitions.py`) only while it holds that run; the Redis adapter decides inside the ack's
WATCH transaction. Stamps compare at the wire's millisecond precision through `fire_stamp`, integer
arithmetic with `stamp_instant` as its exact inverse, because `int(timestamp() * 1000)` writes some
exact-millisecond instants one low and an echoed stamp would never match. A stamp of `0`, what a
body built before the field sends, acks whichever run is held, so a mixed deployment keeps the old
behaviour. A stale or out-of-range stamp returns `acked=false` and logs nothing.

Body side, `BrainTransport` has `list_due_reminders` and `ack_reminder(id, fired_at_unix_ms)`
(`body/crates/rpc/src/reminders.rs`). `RetryingTransport` retries the list and **never the ack**: a
lost reply would make the retry return `acked=false` for the reminder its first attempt cleared. The
next overlay open re-lists whatever is still deliverable. `acked=false` is a state, returned as
`Ok(false)`, and the body has no separate mode for a brain without scheduling.

### 6. Immediate delivery through `BodyService.Notify`

`NotifyRequest` has `title`, `body`, `reminder_id` and `tainted`. `BodyGateway.notify`
(`InMemoryBodyGateway` in `fakes_body.py`) is called whenever the body gateway is configured. A
shown toast counts as delivery, and the ticker acks the run it sent; `false` or `BodyGatewayError`
leaves it deliverable to be fetched instead. Exactly one of the two paths clears a run.

The body renders the toast behind a `Notify` OS trait whose text cannot be interpreted as markup and
whose taint line is fixed application text ([ADR-0066](ADR-0066-reminder-toast-and-card.md)).

### 7. Configuration, wiring and the Redis adapter

`ScheduleConfig` (`config_schedule.py`) reads `CORTEX_SCHEDULE_BACKEND` (`none` by default, so CI
and the no-service loop run without scheduling), `CORTEX_SCHEDULE_POLL_S` (5),
`CORTEX_SCHEDULE_LEASE_S` (300), `CORTEX_SCHEDULE_CLAIM_LIMIT` (8), `CORTEX_SCHEDULE_MAX_ACTIVE`
(32) and `CORTEX_SCHEDULE_TZ` (ADR-0065 decision 1); Redis is `CORTEX_REDIS_URL`. The built-ins
reach `build_cortex_tools` as one pre-assembled sequence from `build_builtin_tools`, which keeps it
under ruff's argument limit; `schedule_builders.py` builds the store, the five tools and the ticker.

`RedisScheduleStore` (`cortex_session/schedules.py`, with `schedule_claims.py` and
`schedule_codec.py`) keeps records durable with no TTL, versioned `{"v": 1, "kind": "schedule"}` and
tolerant of extra keys, so new fields (`anchor`, `rule`, a rule's `zone`) are additive and need no
migration. Keys: `cortex:schedule:{id}` plus the sorted sets `cortex:schedules:due`, `:firing`
(score is the claim time, the lease) and `:deliverable`, and the dead-letter hash
`cortex:schedules:dead`; every `RedisError` becomes `ScheduleStoreError`.

Dead letters are inspected through adapter methods, **not port methods**: `dead_letters()` returns
each quarantined id with its raw bytes rendered with replacement characters, and
`purge_dead_letter(id)` drops one. The in-memory fake can never quarantine, so a port method would
do nothing there, and the raw bytes are hostile or corrupt content that no model tool may read.

### 8. Snooze moves one occurrence

`snooze_scheduled(id, for_seconds)` computes `until` from the injected clock, with the same 60 s to
ten-year bounds as `every_seconds`. The pure `apply_snooze`, shared by both stores, sets `due_at` to
`until`, sets the item back to PENDING and clears deliverability, so a reminder that already ran
runs again fresh. On a recurring item's first snooze it sets `anchor` to the old `due_at`, so the
series keeps its original spacing; a calendar item defines its own times and takes no anchor. FIRING
and unknown ids return `False`. A snooze adds no content, so it needs no taint check, as with
cancel. The tool reads the item first for a precise correction, and the fenced transition gives the
authoritative result.

### 9. Edit changes text and recurrence, never an interval's next due time

`edit_scheduled` changes `text` and the recurrence through one pure `apply_edit` over a
`ScheduleEdit` value. `every_seconds` sets an interval (and clears a rule), `0` stops either form
repeating, and omitting it leaves the recurrence alone. An interval edit leaves `due_at` in place,
so only later reschedulings take the new interval. **Setting a rule is the exception**: a rule
derives its occurrences from the wall clock, so the tool computes the rule's next occurrence and
passes both as one `RuleChange(rule, due_at)`, which reschedules the item as a snooze does (PENDING,
deliverability and `anchor` cleared). Merely moving `due_at` would put a DONE reminder back on the
claim path and run it twice, and the rule branch writes snooze's index set under the same fence.
**Edit ORs the turn's taint onto the item, and a tainted turn cannot edit a task**, since rewriting
the text injects content, as creation does. Results never echo stored text.

### 10. A task's outcome is delivered like a reminder

A task run finishes deliverable and sends its **outcome, never its instruction**, under `TASK_TITLE`
(a reminder uses `REMINDER_TITLE`), through the ticker's `_deliver`; `reminder_to_proto` puts
`last_outcome` in `DueReminder.text` for the fetched path. The deliverable and ack machinery does
not depend on the kind, so this needed no store, proto or overlay change, and a one-shot task's
outcome now survives its run until acked.

## Consequences

- CI covers the values, the port, both stores through one contract suite, the built-ins through a
  real dispatcher, the ticker over fakes with an injected clock, the gRPC handlers and the Rust
  transport methods, all at 100%. The live Redis contract run and an end-to-end run are done by the
  agent in Docker (runbook [scheduling](../runbooks/scheduling.md)); the real toast and card need
  the host (ADR-0066).
- **At-least-once duplicates**: a crash between claim and finish runs the item again after the
  lease; a task running past `CORTEX_SCHEDULE_LEASE_S` is cancelled and re-claimed.
- **A shown toast acks even if nobody saw it**, and a one-shot that already ran then leaves no
  record. The fetched card cannot tell a task from a reminder, since `DueReminder` has no kind.
- A tainted recurring reminder puts attacker text in front of the user repeatedly; it is badged on
  both paths, cannot become a task, and the active cap bounds the volume. The item stores the taint
  bit and no sources, so nothing can say which source tainted it (backlog: provenance).
- Runs share the process with live turns; the claim limit bounds a pass and subagent admission
  (ADR-0012) budgets a task's inference.
- Turning the backend off with deliverables stored strands them until it is enabled again.
- **A sent notification is never re-sent.** The safe retry is the fetched path, which keeps the item
  deliverable until acked. Re-sending would deliver twice unless the body could tell a retry from
  the next run and from a shown toast whose reply was lost. The item id and `deliverable_since`
  already identify a run, so a safe re-send needs that stamp on `NotifyRequest` and a deduplication
  record that outlives the stateless body server, which the OS notification history could hold (a
  toast `Tag`/`Group` per run, unread on a desktop). It waits for a body that reconnects often
  enough between a failed send and the next open to matter.

## Alternatives rejected

- **A Postgres store.** Sessions have no Postgres backend, so it would make a reminder more durable
  than its conversation; nothing queries schedules by provenance, a finished one-shot is deleted and
  the active set is capped, so there is nothing to retain; and with no fake Postgres the fenced
  races could be proven only in an integration suite CI never runs.
- **Per-occurrence history.** Nothing reads a past occurrence: the fetched list shows the one
  deliverable slot and `list_scheduled` the last outcome. It would add a store read, a growth
  policy, an RPC and an overlay view for no reader, and reopens with one.
- **Automated dead-letter expiry.** A quarantined id is dropped from every index in the same
  transaction, so the hash grows only by distinct corrupt records, and expiry would delete the one
  forensic record. If ever wanted, an `hexpire` beside the `hset` is the adapter-local form.
- **Delivery as a `ServerEvent` on `Converse`**: reminders outlive streams.
- **A scheduling sidecar**: a new unit for no isolation gain, since the ticker is stateless.
- **Fencing by status alone**: both claimants see FIRING; the token tells them apart.
- **Snooze or edit moving an interval series**: a daily 09:00 nudged once would become 09:10.

## Related

- [ADR-0065](ADR-0065-wall-clock-schedule-times.md) (display zone and calendar rules) and
  [ADR-0066](ADR-0066-reminder-toast-and-card.md) (the toast and the overlay card).
- Modules: [brain-core](../modules/brain-core.md),
  [brain-orchestrator](../modules/brain-orchestrator.md),
  [brain-session](../modules/brain-session.md), [body-app](../modules/body-app.md).
- Runbook: [scheduling](../runbooks/scheduling.md). ADR-0010 (built-ins), ADR-0012 (admission),
  ADR-0017 (taint routing), ADR-0021 (read RPCs), ADR-0023 (brain to body), ADR-0024 (retries).
