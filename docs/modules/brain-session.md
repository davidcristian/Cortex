# brain/packages/session (`cortex_session`)

**Purpose.** The Redis adapters for the core's stateful ports: `SessionStore` (conversation
history), `TaskStore` (subagent tasks and results), `ScheduleStore` (durable schedules, ADR-0025),
`HandoffStore` (the in-flight brain handoff, ADR-0030) and `PreferenceStore` (the user's settings
record, ADR-0032). This is the state that outlives an orchestrator restart and a model swap
(AGENTS.md, "The one hard rule"). The adapters translate and nothing more: serialization, key layout
and error wrapping, with no domain logic.

## Public contract

`__all__` is the API: the five adapters, `DeadLetter`, `ZoneInfoResolver`, `ZONEINFO_RESOLVER` and
`DEFAULT_REDIS_URL` (`"redis://127.0.0.1:6379/0"`, overridden by `CORTEX_REDIS_URL`, which the
composition root reads and this package never does). Every adapter is built the same two ways, from
an injected `redis.asyncio.Redis` client or from `from_url(url)`, which builds and owns one;
`aclose()` closes that client's connections.

### `RedisSessionStore`

- `append(session_id, message)` RPUSHes one JSON document onto the session's list. It **raises
  `SessionStoreError` for a message with images** (ADR-0029): pixels belong to one turn, the record
  format has no field for them, and storing the message would drop the picture without saying so.
  `InMemorySessionStore` raises the same error, checked over both.
- `history(session_id)` is `LRANGE 0 -1`, decoded in append order. An unknown session has an empty
  history rather than an error.
- `list_sessions(*, limit)` builds the chat list (ADR-0021) in two round trips. The first reads both
  indexes in one transaction: `ZREVRANGE` over the recency index for at most `limit` session ids,
  newest active first, and `SMEMBERS` over `cortex:sessions:hoisted`. The listed set is their union,
  the recency window first and then every hoisted id outside it, deduplicated, so a hoisted chat
  older than the window still appears (ADR-0021 decision 12). The second reads only what a summary
  needs from each listed session, `LRANGE 0 0`, `LRANGE -1 -1`, `LLEN` and `GET :title`, batched
  into one transactional pipeline; the core's `summarize_ends` derives each `SessionSummary` and
  `merge_hoisted` orders the union. The cost is two round trips and two decoded records per chat
  whatever the chat's length (ADR-0021 decision 7). A stale index entry is skipped, and so is a
  corrupt record between the two ends, which a listing never reads. A corrupt record at either end
  fails the listing, and `history` fails on any corrupt record.
- `set_title(session_id, title)` `SET`s a plain string at `cortex:session:{id}:title`, which
  `list_sessions` prefers over the first-message derivation (ADR-0021 decision 9). A later call
  overwrites it and `""` clears the override at read. It is the one write behind both the
  brain-generated title and the overlay's user-driven `RenameSession`.
- `delete(session_id)` removes a whole chat in one transactional pipeline: the message list, the
  title, the recap, the `cortex:sessions` index member and the `cortex:sessions:hoisted` member
  (ADR-0021 decision 11). It is a hard delete rather than a marker, because an unknown session
  already reads as an empty history. It leaves no orphaned key and is idempotent. The memory half of
  the cascade is not here; the orchestrator's `DeleteSession` runs `SessionMemoryCascade` after this
  call.
- `set_recap(session_id, recap)` and `recap(session_id)` hold the summarizing window's account of
  the turns that fell out of it (ADR-0038 decision 9), as one JSON document at
  `cortex:session:{id}:recap` with the text and `covers`, the boundary it accounts for. Both fields
  are stored because the text alone cannot tell a current recap from a stale one. `recap` returns
  `None` for a session that never had one, and fails on a document it cannot read rather than
  returning `None`, which would look the same. `delete` removes it in the same transaction.
- `set_hoisted(session_id, *, hoisted)` adds or removes the chat's id in `cortex:sessions:hoisted`
  (`SADD` or `SREM`, both idempotent), which `list_sessions` unions into every listing. An id in the
  set with no message list is skipped like any other stale index entry. It is the write behind the
  overlay's `SetSessionHoisted`.
- The hoisted set was first stored under `cortex:sessions:pinned`. Before a store first reads or
  writes the set, it moves that key's members into `cortex:sessions:hoisted` with `SUNIONSTORE` and
  `DEL` in one `MULTI`, then sets a flag so later calls skip it. The move is atomic and idempotent,
  so two brains starting at once keep every member, a missing old key moves nothing, and a failed
  move runs again on the next call. `EXISTS cortex:sessions:pinned` is 0 once it has run.

### `RedisTaskStore`

`put_task(task)`, `get_task(task_id)`, `put_result(result)` and `get_result(task_id)` SET and GET
one `SubagentTask` or `SubagentResult` JSON document; an unknown id reads as `None`. Both keys
expire after 3600 s, which is **shorter than the 7200 s a spawn may wait for room** and is
deliberately not ordered against it: the runner reads the task once, before it waits, so the only
read either key has is taken inside the first hour (ADR-0012 decision 16). A spawn admitted after an
hour has no task key left beside its result key.

### `RedisScheduleStore`

The claim-then-finish protocol's meaning lives at the port (a stale token answers `False`; `cancel`
deletes outright and so survives an in-flight fire; terminal items are deleted unless still
deliverable). This adapter maps it onto the key layout below. **Every guarded transition is one
optimistic transaction**: the guard read and the state write share a WATCH, MULTI and EXEC
(`schedule_claims.py` up to the claim, `schedule_delivery.py` after the fire), so a `cancel`, an
`ack` or a re-claim racing the window fails the EXEC as `WatchError`, answered like a stale token
rather than overwritten.

- `add(item)` and `get(item_id)` handle one versioned JSON record per schedule.
- `list_active()` is the union of the three live indexes, loaded and sorted by due time. A stale
  index id is skipped; a record that is present and corrupt fails.
- `cancel(item_id)` deletes the record and every index entry in one MULTI/EXEC, decoding nothing, so
  a corrupt record can still be cancelled.
- `claim_due(now, *, lease, limit)` returns due PENDING ids plus lease-expired FIRING ids, both read
  by score, each moved to FIRING under a fresh uuid token. A record it cannot decode goes to the
  dead-letter hash instead of failing the pass, and candidates past `limit` are released.
- `finish(claim, outcome)` and `release(claim)` are guarded by the record's live token; one
  MULTI/EXEC re-schedules or ends the item, or returns it to PENDING.
- `deliverable()` and `ack(item_id, *, fired_at)` are the fired-reminder delivery slot. The ack
  decides through the pure `acks_fire` inside the same WATCH transaction, so it clears only the fire
  it names, and a fire that finishes between the read and the EXEC fails it.
- `snooze(item_id, *, until)` postpones the next fire through the pure `apply_snooze`. A recurring
  item is allowed: only its next occurrence moves, with `anchor` held at the pre-snooze `due_at` so
  the series keeps its cadence. FIRING and a raced transition answer `False` (ADR-0025 decision 8).
- `edit(item_id, edit)` changes a non-FIRING item's text or recurrence through the pure
  `apply_edit`: a watched `SET` of the re-encoded record, plus a due-index `ZADD` and a deliverable
  `ZREM` when the new rule moves the fire. FIRING, unknown and raced answer `False` (ADR-0025
  decision 9).
- `dead_letters()` and `purge_dead_letter(item_id)` are **adapter-only** operator inspection over
  the quarantine hash, deliberately not port methods, since the fake can never quarantine and no
  core path or model tool reads them. `DeadLetter(item_id, raw)` renders bytes with replacement
  characters so corrupt content stays readable (ADR-0025 decision 7; recipe in the runbook).

### `RedisHandoffStore`

- `put(record)` SETs one `HandoffRecord` JSON document and updates the single active-handoff pointer
  in the same transactional pipeline. A non-terminal record is written with **no expiry**, because
  boot recovery has to find a handoff a crash left behind, and it claims the pointer. A terminal
  record expires after one hour, kept for diagnosis, and releases the pointer when it holds this id.
- `get(handoff_id)` decodes one record; an unknown or expired id reads as `None`. A corrupt record
  fails and names its key, since defaulting the taint fields would fail open after the swap.
- `transition(handoff_id, state, *, failure=None)` is a read, modify and write through `put`, so a
  terminal transition takes its expiry and releases the pointer atomically with the state change. An
  unknown id answers `False`. The reason a settled handoff failed is stored in the same document by
  the same write (ADR-0030 decision 10), so it cannot exist without its state or outlive it; a
  transition naming no reason clears the field.
- `delete(handoff_id)` deletes the record, and the pointer when it names this id, idempotently.
- `active()` follows the pointer to the one in-flight record, `None` when free. A pointer to a
  missing or terminal record reads as no active handoff and nothing is written on that path. The
  read-then-write methods are not guarded against a concurrent writer, because the conductor is the
  store's only writer and `active()` is how it checks.

### `RedisPreferenceStore`

One Redis hash, `cortex:preferences`, one field per setting (ADR-0032). `all()` is a single HGETALL,
the common read since the overlay asks once at startup. `set(key, value)` is an HSET, and an
**empty** value HDELs the field, so a cleared preference is absent rather than present and empty,
and the reader's own default applies. Values are stored as given and never parsed here, so a new
preference costs no change in this package.

## Storage layout

One Redis list per session at `cortex:session:{session_id}:messages`, one JSON object per message:
`{"v": 1, "kind": "message", "role", "text", "at", "turn_id"}`, with `at` an ISO-8601 string
including its UTC offset, preserved rather than normalized to UTC. `v` and `kind` are how a stored
format evolves. The sorted set `cortex:sessions` is the recency index: `append` `ZADD`s the session
id scored by the message's `at`, so the score is the last activity. Batching the two-ended read into
one transactional pipeline took a listing from 23.8 ms to 1.11 ms over 20 chats of 200 messages
against real Redis; the first/last/length cache it replaced is rejected rather than deferred
(ADR-0021 decision 7). The plain set `cortex:sessions:hoisted` holds the hoisted session ids.

Task state uses two string keys per delegation, `cortex:task:{id}` and `cortex:task:{id}:result`,
each one JSON document with a **3600 s expiry**. It is hot and short-lived, written and read back by
one deployment within one turn, so unlike session and memory records it has **no `v` or `kind`
markers**. Timestamps keep their offset. The whole record round-trips, including a task's `model`,
`tainted`, `session_id`, `turn_id` and `item_id` and a result's `tainted` (ADR-0018, ADR-0009
decision 16): the placement inputs, the attribution of whatever spawned the task and the taint
result are what must survive a restart or a swap. Decoding is strict, so a missing key is a corrupt
record.

Handoff state (ADR-0030) is hot the same way: one record at `cortex:handoff:{id}`, no `v` or `kind`
markers, plus the pointer key `cortex:handoff:active` holding the in-flight record's id (one GPU, at
most one swap at a time). The document holds the escalation `brief`, the turn's fence `nonce`, the
whole taint ledger (`tainted`, `opaque`, `sources` as ordered `{"kind", "value"}` pairs,
`untrusted_urls` stored sorted and read back as a set), the budget position (`budget_remaining` and
`budget_closed`), `rounds_used`, `loop_tail` (each message with its `tool_calls` as
`{"id", "name", "arguments"}`; the transient dispatch stamp is never stored) and `failure`, the only
field written after the snapshot. `failure` is required like the rest, since reading a missing field
as "no reason given" would be indistinguishable from the state the field exists to describe.
Decoding is strict for the same reason as task state: taint fields that quietly defaulted would fail
open after the swap.

Schedule state (ADR-0025) is durable again: one record per schedule at `cortex:schedule:{id}`
holding
`{"v": 1, "kind": "schedule", "id", "item_kind", "text", "session_id", "due_at", "created_at", "every_s", "rule", "anchor", "model", "tainted", "status", "deliverable_since", "last_outcome", "claim", "claimed_at"}`
with **no expiry**, since the task store's would drop reminders. `anchor` and `rule` are
**additive** keys read with `.get` and no version bump, so a record predating either decodes as
absent. `rule` is the nested `{"hour", "minute"}` calendar recurrence plus its day selector, read
strictly when present so a malformed one fails rather than degrading to a one-shot. Which selector
it holds is **which key is present**: `days` (weekday numbers) for a weekly rule, `month_days`
(calendar days) for a monthly one, so a record written before day-of-month selectors reads back as
the weekly rule it was (ADR-0065 decision 3). A rule with its own timezone has an additive `zone`
key holding the IANA name, which decode resolves back to a `DisplayZone` through `ZoneInfoResolver`
(`zone_resolver.py`), so the store's `decode` call sites are unchanged. A rule with no `zone` key
decodes without one and the deployment zone applies; a stored name that no longer resolves is a
corrupt record, failing and naming the key rather than substituting the deployment zone (ADR-0065
decision 4). The `claim` token and `claimed_at` are adapter mechanics stored inside the record; the
domain `ScheduledItem` has neither. Three sorted sets drive the ticker and delivery,
`cortex:schedules:due` (score: due-at epoch), `cortex:schedules:firing` (score: claim epoch, the
lease) and `cortex:schedules:deliverable` (score: fired-at epoch), plus the dead-letter hash
`cortex:schedules:dead`. Every record and index update is one MULTI/EXEC, so a crash cannot separate
a record from its indexes.

## Record format policy

- **New optional keys are safe.** A reader touches only the keys it is written to read, so extra
  keys from a newer writer are ignored.
- **New kinds or versions break old readers.** A reader that meets an unknown `kind` or an
  unsupported `v` fails on the whole history, so **deploy readers before writers**.
- Records with no `v` or `kind`, written before the markers existed, decode as `kind "message"`,
  `v 1`.
- One unreadable record **stops the session with an error** naming the record's list index, kind and
  version, rather than being skipped. This is a single-user system, so a stop that names the bad
  record costs less than a dropped one, which would corrupt a future handoff's context.

## Error contract

Every Redis or connection failure, and every corrupt or unreadable stored record, is raised as the
core's `SessionStoreError`, `TaskStoreError`, `ScheduleStoreError` or `HandoffStoreError`. Backend
failures keep the original exception as `__cause__`; decode failures name the record (the session
store by list index plus kind and version, the others by key). No `redis.exceptions.*` type crosses
a port. The one place that does not fail loudly is the schedule **claim path**, where a corrupt
record is quarantined instead (ADR-0025).

## Tests

Each port has one shared behaviour suite driven over the in-memory implementation and the Redis one
on fakeredis: `tests/contract.py`, `tests/task_contract.py`, `tests/schedule_contract.py` and
`tests/handoff_contract.py`. Adapter-only mechanics (error wrapping per operation, codec policy,
quarantine, stale-id tolerance, surplus release, expiry, pointer self-repair and the hoisted set's
move, in `tests/test_hoisted_key_move.py`) are tested against the Redis adapter alone. The schedule
suite is about the guarded protocol: a stale finish rejected, a cancel during a fire sticking, a
re-claim under a fresh token after lease expiry, terminal cleanup, taint OR at fire time, and the
delivery lifecycle. The handoff suite's central check is the taint ledger round trip, where a ledger
built through the real `TaintLedger` API comes back exact in bytes, order and set membership through
`HandoffRecord.taint_ledger()`, with the `opaque` bit checked at both values because both of its
consumers start from `False` after a swap.

Every session check reaches CI through `contract.ALL_CHECKS`, which `tests/test_store_contract.py`
parametrizes over the two-implementation fixture, rather than through hand-written wrappers a new
check has to be added to twice ([ADR-0068](../adr/ADR-0068-port-contract-lists.md) decision 1).

The `integration`-marked `tests/test_store_live.py`, `tests/test_handoff_live.py` and
`tests/test_schedule_live.py` run the same suites against real Redis (excluded from CI and coverage
by the workspace addopts; run with
`cd brain && uv run pytest -m integration --no-cov packages/session`, where `--no-cov` matters
because the 100% threshold in addopts would otherwise fail the run). All three take their store from
`tests/live_redis.py`, the one place that defines how a live run is isolated: it rewrites
`CORTEX_REDIS_URL` onto its own logical database (`LIVE_DB`, database 15, which production never
selects) and its `reset` empties that database before the suite and after every check, a failing
check included. Each check therefore starts from the same empty store the fakeredis fixture gives
it, and no real session, schedule or handoff is touched. Two guards keep the flush off a production
database: the URL rewrite fails when `CORTEX_REDIS_URL` already selects `LIVE_DB`, and `reset`
re-reads the database its client actually opened before flushing. None of this reaches the adapters,
which keep their key layouts and took no prefix, namespace or database argument (ADR-0002 decision
14).

## Invariants

- State outlives every process: nothing is cached in an adapter and every read reaches Redis. Two
  stores, or two orchestrator processes, over the same URL see the same sessions.
- The stored formats above are the contract. Extend them; do not repurpose a field.
- Fully typed (PEP 561 `py.typed`), pyright strict clean, and 100% line and branch covered by the
  contract suites. The live suites add no coverage by design.

**Dependencies.** cortex-core (workspace) and redis (the asyncio client). Dev-only from the
workspace root: fakeredis, which is what runs the contract suites without a server.
