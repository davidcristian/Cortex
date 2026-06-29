# brain/packages/session (`cortex_session`)

**Purpose.** The Redis adapter for the core's `SessionStore` port, holding the hot state that
survives orchestrator restarts and model swaps (the one hard rule). A translator only:
serialization, key layout, and error wrapping; no business logic.

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
- `DEFAULT_REDIS_URL` is `"redis://127.0.0.1:6379/0"`. Deployments override via
  `CORTEX_REDIS_URL`, read by the composition root (orchestrator settings), never by
  this adapter.

**Storage layout.** One Redis list per session, key `cortex:session:{session_id}:messages`;
one JSON object per message: `{"v": 1, "kind": "message", "role", "text", "at", "turn_id"}`
with `at` as an ISO-8601 string carrying its UTC offset. Roundtrip is exact for role,
text, tz-aware timestamp (offset preserved, not normalized to UTC), and turn id.
`v`/`kind` are the schema escape hatch for evolving persisted records.

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

**Error contract.** Every Redis/connection failure and every corrupt or unreadable
stored record is raised as the core's `SessionStoreError`; backend failures carry the
original exception chained as `__cause__`, and decode failures name the offending
record's list index (plus kind and version for unsupported shapes); no
`redis.exceptions.*` type ever crosses the port.

**Contract tests.** `tests/contract.py` is one shared behavior suite (empty history,
append→history order, multi-session isolation, roundtrip fidelity incl. timezone) run
against BOTH implementations (`InMemorySessionStore` and `RedisSessionStore` over
fakeredis) plus fakeredis-injected failure tests for the error wrapping. The
integration-marked test in `tests/test_store_live.py` runs the same suite against real
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
