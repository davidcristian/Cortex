# brain/packages/session (`cortex_session`)

**Purpose.** The Redis adapters for the core's stateful ports, `SessionStore` (conversation
history), `TaskStore` (subagent tasks + results), and `ScheduleStore` (durable schedules,
ADR-0025), the state that survives orchestrator restarts and model swaps (the one hard rule).
Translators only: serialization, key layout, and error wrapping; no business logic.

**Public contract** (everything importable from `cortex_session`; `__all__` is the API):

- `RedisSessionStore` implements the `SessionStore` port over redis-py asyncio:
  - `RedisSessionStore(client: redis.asyncio.Redis)` takes an injected client (the contract
    tests inject fakeredis here).
  - `RedisSessionStore.from_url(url: str = DEFAULT_REDIS_URL)` builds and owns a
    client for `url`; release it via `aclose()` at composition-root shutdown.
  - `async append(session_id, message)` RPUSHes one JSON document onto the session's
    list.
  - `async history(session_id)` is LRANGE 0..-1, decoded in append order; an unknown
    session is an empty history, not an error.
  - `async list_sessions(*, limit)` builds the chat list (ADR-0021): ZREVRANGE the recency
    index for at most `limit` session ids newest-active first, load each session's history
    (reusing `history`), and derive its `SessionSummary` via the core `summarize_session`
    (derivation is domain logic, since the adapter only enumerates and translates). A dangling
    index entry (id present, message list gone) is skipped, not fatal.
  - `async aclose()` closes the underlying client's connections.
- `RedisTaskStore` implements the `TaskStore` port over redis-py asyncio (ADR-0010), same
  injected-client / `from_url` / `aclose` shape as above:
  - `async put_task(task)` / `async get_task(task_id)` SET/GET one `SubagentTask` JSON
    document (unknown id → `None`).
  - `async put_result(result)` / `async get_result(task_id)` SET/GET one `SubagentResult`
    JSON document (unknown id → `None`).
- `RedisScheduleStore` implements the `ScheduleStore` port over redis-py asyncio
  (ADR-0025), same injected-client / `from_url` / `aclose` shape as above. The fenced
  claim→finish protocol's *semantics* live at the port (a stale token no-ops `False`;
  `cancel` deletes outright and so sticks through an in-flight fire; terminal items are
  deleted unless deliverable); this adapter translates them onto the key layout below.
  **Every guarded transition is optimistically atomic** (post-review hardening): the
  guard read and the state write share one WATCH→MULTI/EXEC transaction (the helpers in
  `schedule_claims.py`, split out for the line cap), so a `cancel`/`ack`/re-claim racing
  the window makes the write's EXEC fail as `WatchError`, which is answered like a stale token,
  never silently overwritten:
  - `async add(item)` / `async get(item_id)` handle one versioned JSON record per schedule.
  - `async list_active()` is the union of the three live indexes, records loaded and sorted by
    due time (dangling index ids skipped; a present-but-corrupt record fails loudly).
  - `async cancel(item_id)` deletes the record + every index entry in one MULTI/EXEC (never
    decodes, so a corrupt record is cancellable too).
  - `async claim_due(now, *, lease, limit)` returns due PENDING ids plus lease-expired FIRING
    ids (both score-bounded reads), each moved to FIRING under a fresh uuid token; an
    undecodable record is **quarantined** to the dead-letter hash instead of failing the
    pass; candidates merged past `limit` are released back (bounded surplus).
  - `async finish(claim, outcome)` / `async release(claim)` are guarded by the record's
    live token; one MULTI/EXEC re-arms/terminates (finish) or returns to PENDING (release).
  - `async deliverable()` / `async ack(item_id)` are the fired-reminder delivery slot.
  - `async snooze(item_id, *, until)` postpones a one-shot (PENDING re-scored in the due
    index; a fired-but-undelivered reminder re-arms off the deliverable index), refusing a
    recurring or FIRING item and answering a raced transition `False` like the rest
    (ADR-0025 snooze addendum).
  - `async edit(item_id, edit)` retexts / re-recurs a non-FIRING item: a bare watched `SET` of
    the re-encoded record (`due_at` untouched, so the due/firing/deliverable indexes need no
    write), applying the pure `apply_edit` the fake shares; FIRING and unknown answer `False`,
    raced transitions `False` like the rest (ADR-0025 edit addendum).
  - `async dead_letters() -> Sequence[DeadLetter]` / `async purge_dead_letter(item_id)` are
    **adapter-only** operator inspection over the quarantine hash (deliberately not port
    methods: the fake can never quarantine, and no core path or model tool consumes them);
    `DeadLetter(item_id, raw)` renders bytes with replacement characters so corrupt content
    stays inspectable (ADR-0025 dead-letter addendum, runbook recipe in scheduling.md).
- `DEFAULT_REDIS_URL` is `"redis://127.0.0.1:6379/0"`. Deployments override via
  `CORTEX_REDIS_URL`, read by the composition root (orchestrator settings), never by
  this adapter.

**Storage layout.** One Redis list per session, key `cortex:session:{session_id}:messages`;
one JSON object per message: `{"v": 1, "kind": "message", "role", "text", "at", "turn_id"}`
with `at` as an ISO-8601 string carrying its UTC offset. Roundtrip is exact for role,
text, tz-aware timestamp (offset preserved, not normalized to UTC), and turn id.
`v`/`kind` are the schema escape hatch for evolving persisted records. A sorted set
`cortex:sessions` is the recency index for `list_sessions` (ADR-0021): `append` `ZADD`s the
session id scored by the message's `at` (last append wins → the score is last-activity),
and `list_sessions` reads it with `ZREVRANGE`. The N+1 reads it does (one `LRANGE` per
listed session) are fine for a personal system's recent list; caching each session's
first/last/length in the index is a deferred perf refinement behind the unchanged port.

Task state uses two string keys per delegation: `cortex:task:{id}` (the `SubagentTask`) and
`cortex:task:{id}:result` (the `SubagentResult`), each one JSON document written with a **1-hour
TTL**. Task state is *hot and ephemeral* (it lives only for the in-flight delegation, written
and read back by one deployment within one turn), so unlike session/memory records it carries
**no `v`/`kind` markers**. Timestamps preserve their offset the same way. The whole record
round-trips, with a task's `model`/`tainted` and a result's `tainted` included (ADR-0018): the
resolution inputs and the taint verdict are exactly what must survive a restart or swap
mid-delegation (taint that did not would fail open), and both decode strictly (a missing key is
a corrupt record, no legacy paths, since ephemeral records need none).

Schedule state (ADR-0025) is the durable retention class again: one record per schedule at
`cortex:schedule:{id}` storing `{"v": 1, "kind": "schedule", "id", "item_kind", "text",
"session_id", "due_at", "created_at", "every_s", "model", "tainted", "status",
"deliverable_since", "last_outcome", "claim", "claimed_at"}` with **no TTL** (the task
store's expiry would silently drop reminders) and the session store's `v`/`kind` markers +
evolution policy. The fencing `claim` token and `claimed_at` are adapter mechanics persisted
inside the record; the domain `ScheduledItem` never carries them. Three ZSET indexes drive
the ticker and delivery. They are `cortex:schedules:due` (score = due-at epoch),
`cortex:schedules:firing` (score = claim epoch, the lease), `cortex:schedules:deliverable`
(score = fired-at epoch), plus the dead-letter hash `cortex:schedules:dead` holding
quarantined raw records for forensics (retention/inspection tooling is a recorded deferral).
Every record+index update runs as one MULTI/EXEC pipeline, so a crash cannot orphan a record
from its indexes.

**Record evolution policy.**
- *New optional keys are safe*: the reader touches only the keys it knows, so extra
  keys added by a newer writer are ignored (forward-compatible additions).
- *New kinds or versions are breaking for old readers*: a reader that meets an
  unknown `kind` or unsupported `v` refuses the whole history, so **deploy readers
  before writers** when introducing either.
- Records missing `v`/`kind` (written before the markers existed) decode as
  `kind "message"`, `v 1`.
- Accepted tradeoff: one unreadable record **blocks the session loudly** (the error
  names the record's list index, kind, and version) instead of being skipped. This
  is a single-user system. A loud, diagnosable stop beats a silently dropped record
  that would invisibly corrupt the context of a future handoff.

**Error contract.** Every Redis/connection failure and every corrupt or unreadable stored
record is raised as the core's `SessionStoreError` (session), `TaskStoreError` (task), or
`ScheduleStoreError` (schedule); backend failures carry the original exception chained as
`__cause__`, decode failures name the offending record (session: list index + kind/version;
task/schedule: the key); no `redis.exceptions.*` type ever crosses the port. The one
exception to fail-loud is the schedule **claim path**, where a corrupt record quarantines
(ADR-0025's poison-pill defense) rather than raising.

**Contract tests.** `tests/contract.py` is one shared behavior suite (empty history,
append→history order, multi-session isolation, roundtrip fidelity incl. timezone, and
`list_sessions` recency-ordering + title/preview derivation) run against BOTH
implementations (`InMemorySessionStore` and `RedisSessionStore` over fakeredis) plus
fakeredis-injected failure tests for the error wrapping (append, history, list, close) and
Redis-specific `list_sessions` edges (empty store, limit, dangling index entry). The
`list_sessions` check filters the global list to the ids it created, so it is safe against
a shared live server. `tests/task_contract.py`
does the same for the `TaskStore` (missing→None, task/result round-trip, timezone fidelity) over
`InMemoryTaskStore` and `RedisTaskStore`, plus disconnected/corrupt-record failure tests.
`tests/schedule_contract.py` does it for the `ScheduleStore`. The fenced protocol is the
point of that suite (stale finish rejected, cancel-during-fire sticks, lease-expiry re-claim
under a fresh token, terminal cleanup, fire-time taint OR, delivery lifecycle), and it runs over
`InMemoryScheduleStore` and `RedisScheduleStore`, with adapter-only mechanics (error wrapping
per operation, codec policy, quarantine, dangling-id tolerance, surplus release) tested against
the Redis adapter alone. The integration-marked tests in `tests/test_store_live.py` and
`tests/test_schedule_live.py` run the suites against real Redis at `CORTEX_REDIS_URL`
(excluded from CI/coverage by the workspace addopts; run manually:
`cd brain && uv run pytest -m integration --no-cov packages/session`. Here the `--no-cov`
matters, the 100% gate in addopts would otherwise fail the run) and clean up the keys they
create; the schedule live test additionally **skips when real schedules exist** (its checks
assert exact global views and claim whatever is due, so it refuses to disturb them).

**Invariants.**
- State outlives every process: nothing is cached in the adapter; every read hits
  Redis. Two stores (or two orchestrator processes) over the same URL see the same
  sessions.
- The JSON schema above is the persisted contract. Extend, don't repurpose fields.
- Fully typed (PEP 561 `py.typed`); pyright strict clean; 100% line+branch covered by
  the contract suite (the live suite adds no coverage by design).

**Dependencies.** cortex-core (workspace), redis (asyncio client). Dev-only (workspace
root): fakeredis (contract tests without a server).
