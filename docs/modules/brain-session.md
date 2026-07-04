# brain/packages/session (`cortex_session`)

**Purpose.** The Redis adapters for the core's hot-state ports, `SessionStore` (conversation
history) and `TaskStore` (subagent tasks + results), the state that survives orchestrator
restarts and model swaps (the one hard rule). Translators only: serialization, key layout, and
error wrapping; no business logic.

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
  - `async aclose()` closes the underlying client's connections.
- `RedisTaskStore` implements the `TaskStore` port over redis-py asyncio (ADR-0010), same
  injected-client / `from_url` / `aclose` shape as above:
  - `async put_task(task)` / `async get_task(task_id)` SET/GET one `SubagentTask` JSON
    document (unknown id → `None`).
  - `async put_result(result)` / `async get_result(task_id)` SET/GET one `SubagentResult`
    JSON document (unknown id → `None`).
- `DEFAULT_REDIS_URL` is `"redis://127.0.0.1:6379/0"`. Deployments override via
  `CORTEX_REDIS_URL`, read by the composition root (orchestrator settings), never by
  this adapter.

**Storage layout.** One Redis list per session, key `cortex:session:{session_id}:messages`;
one JSON object per message: `{"v": 1, "kind": "message", "role", "text", "at", "turn_id"}`
with `at` as an ISO-8601 string carrying its UTC offset. Roundtrip is exact for role,
text, tz-aware timestamp (offset preserved, not normalized to UTC), and turn id.
`v`/`kind` are the schema escape hatch for evolving persisted records.

Task state uses two string keys per delegation: `cortex:task:{id}` (the `SubagentTask`) and
`cortex:task:{id}:result` (the `SubagentResult`), each one JSON document written with a **1-hour
TTL**. Task state is *hot and ephemeral* (it lives only for the in-flight delegation, written
and read back by one deployment within one turn), so unlike session/memory records it carries
**no `v`/`kind` markers**. Timestamps preserve their offset the same way. The whole record
round-trips, with a task's `model`/`tainted` and a result's `tainted` included (ADR-0018): the
resolution inputs and the taint verdict are exactly what must survive a restart or swap
mid-delegation (taint that did not would fail open), and both decode strictly (a missing key is
a corrupt record, no legacy paths, since ephemeral records need none).

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
record is raised as the core's `SessionStoreError` (session) or `TaskStoreError` (task);
backend failures carry the original exception chained as `__cause__`, decode failures name the
offending record (session: list index + kind/version; task: the key); no `redis.exceptions.*`
type ever crosses the port.

**Contract tests.** `tests/contract.py` is one shared behavior suite (empty history,
append→history order, multi-session isolation, roundtrip fidelity incl. timezone) run
against BOTH implementations (`InMemorySessionStore` and `RedisSessionStore` over
fakeredis) plus fakeredis-injected failure tests for the error wrapping. `tests/task_contract.py`
does the same for the `TaskStore` (missing→None, task/result round-trip, timezone fidelity) over
`InMemoryTaskStore` and `RedisTaskStore`, plus disconnected/corrupt-record failure tests. The
integration-marked test in `tests/test_store_live.py` runs the session suite against real
Redis at `CORTEX_REDIS_URL` (excluded from CI/coverage by the workspace addopts; run
manually: `cd brain && uv run pytest -m integration --no-cov packages/session`. The
`--no-cov` matters, the 100% gate in addopts would otherwise fail the run) and cleans
up the keys it creates.

**Invariants.**
- State outlives every process: nothing is cached in the adapter; every read hits
  Redis. Two stores (or two orchestrator processes) over the same URL see the same
  sessions.
- The JSON schema above is the persisted contract. Extend, don't repurpose fields.
- Fully typed (PEP 561 `py.typed`); pyright strict clean; 100% line+branch covered by
  the contract suite (the live suite adds no coverage by design).

**Dependencies.** cortex-core (workspace), redis (asyncio client). Dev-only (workspace
root): fakeredis (contract tests without a server).
