# brain/packages/session (`cortex_session`)

**Purpose.** The Redis adapters for the core's stateful ports, `SessionStore` (conversation
history), `TaskStore` (subagent tasks + results), `ScheduleStore` (durable schedules,
ADR-0025), `HandoffStore` (the in-flight brain handoff, ADR-0030), and `PreferenceStore` (the
user's settings record, ADR-0032), the state that survives
orchestrator restarts and model swaps (the one hard rule).
Translators only: serialization, key layout, and error wrapping; no business logic.

**Public contract** (everything importable from `cortex_session`; `__all__` is the API):

- `RedisPreferenceStore` implements the `PreferenceStore` port over ONE Redis hash,
  `cortex:preferences`, one field per setting (ADR-0032). `all()` is a single HGETALL (the common
  read: the overlay asks once at startup), `set(key, value)` is an HSET, and an EMPTY value HDELs
  the field, so a cleared preference is absent rather than present-and-empty and the reader's own
  default applies. Values are stored verbatim and never parsed here, which is what lets a new
  preference cost no change in this package. Same constructor pair as the other adapters
  (injected client or `from_url`), same `PreferenceStoreError` wrapping with the cause chained.
- `RedisSessionStore` implements the `SessionStore` port over redis-py asyncio:
  - `RedisSessionStore(client: redis.asyncio.Redis)` takes an injected client (the contract
    tests inject fakeredis here). Its keys and both record codecs (message and recap) live in
    `store_codec.py`, split out for the line cap when the recap arrived (the `handoff_codec` /
    `schedule_codec` precedent) and a real seam: that module owns the storage format, `store.py`
    owns the round trips and the error wrapping.
  - `RedisSessionStore.from_url(url: str = DEFAULT_REDIS_URL)` builds and owns a
    client for `url`; release it via `aclose()` at composition-root shutdown.
  - `async append(session_id, message)` RPUSHes one JSON document onto the session's
    list. **Raises `SessionStoreError` on an image-bearing message** (ADR-0029): pixels are
    turn-local, the record schema has no field for them, and accepting one would silently drop
    the picture rather than store it. `InMemorySessionStore` refuses it identically, and the
    shared contract suite runs the check against both, so a fake that accepted what the real
    store rejects cannot let the invariant pass CI and fail in production.
  - `async history(session_id)` is LRANGE 0..-1, decoded in append order; an unknown
    session is an empty history, not an error.
  - `async list_sessions(*, limit)` builds the chat list (ADR-0021): round trip one reads BOTH
    indexes in one transaction, ZREVRANGE the recency index for at most `limit` session ids
    newest-active first AND SMEMBERS the pinned set (`cortex:sessions:pinned`, ADR-0021 pinning
    addendum). Their UNION is the listed set (recency window first, then every pinned id outside
    it, deduplicated), so a pinned chat OLDER than the recency window still lists, which is the
    whole point of pinning; a chat both pinned and inside the window appears once. Round trip two
    reads only what a summary is derived from, each listed session's first record, last record,
    length, and title (`LRANGE 0 0`, `LRANGE -1 -1`, `LLEN`, `GET :title`), all batched into one
    transactional pipeline, and derives its `SessionSummary` via the core `summarize_ends` with
    `pinned=` set from the pinned-set membership (derivation is domain logic; the adapter only
    enumerates and translates). The core `merge_pinned` then orders the union pinned-first,
    recency-descending within each group. Still two round trips and two decoded records per chat,
    whatever the chat's length (ADR-0021 bounded-reads addendum); the listed count is the window
    plus the pinned chats outside it, and the pinned set is small by construction. A dangling
    index entry (id present, message list gone, e.g. a pin on a since-deleted id) is skipped, not
    fatal; so is a corrupt record *between* the ends, which a listing never reads (`history` still
    fails loudly on it, and a corrupt record at either end still fails the listing). The
    `title_override` is the stored title (ADR-0021 titles addendum).
  - `async set_title(session_id, title)` `SET`s a plain string at `cortex:session:{id}:title`
    (a display title, ADR-0021 titles addendum), which `list_sessions` prefers over the
    first-message derivation; a later call overwrites it, and `""` clears the override at read.
    Its own key, so it carries no `v`/`kind` markers; not conversation content, but stored beside
    it so it survives a swap. This is the catalog write behind **both** the brain-generated title
    and the overlay's user-driven `RenameSession` (ADR-0021 management addendum); the store does
    not distinguish them, so no new port method was needed to add rename.
  - `async delete(session_id)` HARD-deletes a whole chat: the message list (`:messages`), the
    optional title (`:title`), the optional recap (`:recap`, ADR-0038 decision 9), the
    `cortex:sessions` recency-index member, and the
    `cortex:sessions:pinned` member (ADR-0021 pinning addendum), all in one transactional pipeline
    so a listing never sees a half-deleted chat (ADR-0021 delete addendum). The destructive "forget
    this chat" write. Hard, not a tombstone: reads are snapshots and an unknown session already
    reads as an empty history, so a deleted chat degrades cleanly with no in-flight id to protect
    (the memory `delete_scope` reasoning). It leaves no orphaned key, dangling index entry, or
    dangling pin, and is idempotent (`DEL`/`ZREM`/`SREM` on absent keys/members are no-ops), so a
    retry after a failure heals. The memory half of the cascade is NOT here (memory is a separate
    store); the orchestrator's `DeleteSession` composes this delete with `SessionMemoryCascade`.
  - `async set_recap(session_id, recap)` / `async recap(session_id)` hold the summarizing
    window's account of the turns that fell out of the window (ADR-0038 decision 9), as one JSON
    document at `cortex:session:{id}:recap` carrying `v`/`kind` like a message record: the text
    and `covers`, the boundary it accounts for. Both halves are on the wire because a reader with
    the text alone could not tell a current recap from a stale one. `recap` answers `None` for a
    session that never had one written, and fails loudly on a document this reader cannot read
    rather than answering `None`, which would look exactly like a session never summarized. A
    later `set_recap` overwrites. The pair sits on this port rather than one of its own because a
    recap's lifetime IS the session's, so `delete` removes it in the same transaction: it is a
    model's account of the same conversation and exactly as private as the transcript. Derived
    and disposable, but stored beside the messages so it survives a model swap, which is the
    whole reason the summarizer caches rather than recomputes.
  - `async set_pinned(session_id, *, pinned)` toggles the chat's membership in the pinned set
    (ADR-0021 pinning addendum): `SADD cortex:sessions:pinned` when pinning, `SREM` when unpinning,
    both idempotent by value. `list_sessions` unions the pinned set into every listing, so a pinned
    chat lists regardless of recency. Not conversation content but stored beside it so a pin
    survives a swap; a pin on an unknown or since-deleted id is benign (a pinned member with no
    message list, which `list_sessions` skips like any dangling index entry). This is the catalog
    write behind the overlay's user-driven `SetSessionPinned`.
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
  `schedule_claims.py` up to and including the claim, `schedule_delivery.py` for everything
  after the fire, both split out for the line cap), so a `cancel`/`ack`/re-claim racing
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
  - `async snooze(item_id, *, until)` postpones the next fire via the pure `apply_snooze`
    (PENDING re-scored in the due index; a fired-but-undelivered reminder re-arms off the
    deliverable index). A recurring item is allowed: only its next occurrence moves, `anchor`
    pinned to the pre-snooze `due_at` so the series keeps its cadence. FIRING refuses, and a
    raced transition answers `False` like the rest (ADR-0025 occurrence-snooze addendum).
  - `async edit(item_id, edit)` retexts / re-recurs a non-FIRING item: a bare watched `SET` of
    the re-encoded record (`due_at` untouched, so the due/firing/deliverable indexes need no
    write, plus a due-index `ZADD` and a deliverable `ZREM` when a rule change moves the
    fire), applying the pure `apply_edit` the fake shares; FIRING and unknown answer `False`,
    raced transitions `False` like the rest (ADR-0025 edit addendum).
  - `async dead_letters() -> Sequence[DeadLetter]` / `async purge_dead_letter(item_id)` are
    **adapter-only** operator inspection over the quarantine hash (deliberately not port
    methods: the fake can never quarantine, and no core path or model tool consumes them);
    `DeadLetter(item_id, raw)` renders bytes with replacement characters so corrupt content
    stays inspectable (ADR-0025 dead-letter addendum, runbook recipe in scheduling.md).
- `RedisHandoffStore` implements the `HandoffStore` port over redis-py asyncio (ADR-0030),
  same injected-client / `from_url` / `aclose` shape as above (codec split into
  `handoff_codec.py` for the line cap):
  - `async put(record)` SETs one `HandoffRecord` JSON document and keeps the single
    active-handoff pointer true to its state in the same transactional pipeline: a
    non-terminal record is written with **no TTL** (boot recovery must find a crash-stranded
    handoff) and claims the pointer; a terminal one is written under a 1-hour diagnosis TTL
    and releases the pointer when it holds this id.
  - `async get(handoff_id)` GET/decodes one record (unknown/expired id → `None`); a corrupt
    record fails loudly naming its key, since silently defaulting the taint fields would fail
    open after the swap.
  - `async transition(handoff_id, state)` is a read-modify-write through `put`, so a terminal
    transition inherits its TTL and pointer release atomically with the state change; an
    unknown id no-ops `False`.
  - `async delete(handoff_id)` DELs the record and the pointer when it names it, idempotently.
  - `async active()` follows the pointer to the one in-flight record (`None` when free); a
    dangling pointer or a hand-crafted terminal record behind it reads as no active handoff,
    read-only (nothing is mutated on the read path). The read-then-write verbs are not fenced
    against a concurrent writer: the conductor is the store's one writer by construction
    (`active()` is how it checks that), unlike the multi-claimant schedule store.
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
and `list_sessions` reads it with `ZREVRANGE`, then batches each listed session's two-ended
read into one transactional pipeline (the `LLEN` rides along so the tail record keeps its true
index in an error, and rides the same transaction so the length and the record it names are one
snapshot; a `GET` of the session's `cortex:session:{id}:title` key rides along too, a
brain-generated display title that overrides the first-message one when set, ADR-0021 titles
addendum). Measured 23.8 ms to 1.11 ms on 20 chats of 200 messages against real Redis; the
first/last/length index cache this refinement replaced is rejected, not deferred (ADR-0021
bounded-reads addendum). A plain set `cortex:sessions:pinned` holds the pinned session ids
(ADR-0021 pinning addendum): `set_pinned` maintains it (`SADD`/`SREM`), `delete` clears its
member, and `list_sessions` reads it (`SMEMBERS`, batched with the `ZREVRANGE` so round trip one
still reads both indexes at once) and unions it with the recency window so a pinned chat lists
regardless of recency.

Task state uses two string keys per delegation: `cortex:task:{id}` (the `SubagentTask`) and
`cortex:task:{id}:result` (the `SubagentResult`), each one JSON document written with a **1-hour
TTL**. Task state is *hot and ephemeral* (it lives only for the in-flight delegation, written
and read back by one deployment within one turn), so unlike session/memory records it carries
**no `v`/`kind` markers**. Timestamps preserve their offset the same way. The whole record
round-trips, with a task's `model`/`tainted` and a result's `tainted` included (ADR-0018): the
resolution inputs and the taint verdict are exactly what must survive a restart or swap
mid-delegation (taint that did not would fail open), and both decode strictly (a missing key is
a corrupt record, no legacy paths, since ephemeral records need none).

Handoff state (ADR-0030) is hot like task state: one record at `cortex:handoff:{id}` (one JSON
document, no `v`/`kind` markers, written and read back within one handoff by one deployment,
the task-store precedent) plus the pointer key `cortex:handoff:active` holding the in-flight
record's id (one GPU, at most one swap at a time). The document carries the escalation `brief`,
the turn's fence `nonce`, the whole taint ledger (`tainted`, `opaque`, `sources` as ordered
`{"kind", "value"}` pairs, `untrusted_urls` stored sorted and read back as a set), the budget
position (`budget_remaining`/`budget_closed`), `rounds_used`, and `loop_tail` (each message
with its `tool_calls` as `{"id", "name", "arguments"}`; the transient dispatch stamp is never
persisted, per the core's `ToolCall` contract). Timestamps preserve their offset as
everywhere. Non-terminal records carry **no TTL**; terminal (`done`/`failed`) records expire
after an hour, kept only for diagnosis. Decode is strict (a missing key is a corrupt record,
no legacy paths): taint fields that silently defaulted would fail open after the swap, which
is the exact laundering/taint gap the contract round trip pins shut.

Schedule state (ADR-0025) is the durable retention class again: one record per schedule at
`cortex:schedule:{id}` storing `{"v": 1, "kind": "schedule", "id", "item_kind", "text",
"session_id", "due_at", "created_at", "every_s", "rule", "anchor", "model", "tainted", "status",
"deliverable_since", "last_outcome", "claim", "claimed_at"}` with **no TTL** (the task
store's expiry would silently drop reminders) and the session store's `v`/`kind` markers +
evolution policy. `anchor` and `rule` are **additive** keys read with `.get` and no version
bump (a record predating either decodes as absent); `rule` is the nested
`{"hour", "minute"}` calendar recurrence plus its day selector, read strictly when present so a
malformed one fails loudly rather than degrading to a one-shot. Which selector it carries is
**which key is present**, not a discriminator: `days` (weekday numbers) for a weekly rule,
`month_days` (calendar days) for a monthly one, so a record written before day-of-month
selectors reads back as the weekly rule it was (ADR-0025 monthly addendum). A rule that named
its own timezone carries an additive `zone` key (its IANA name); decode **self-resolves** it
back to a `DisplayZone` through `ZoneInfoResolver` (`zone_resolver.py`, the `zoneinfo`-backed
`ZoneResolver` the composition root also injects into the schedule tools), so the store's
`decode` call sites stay untouched. A rule with no `zone` key decodes zone-less (the deployment
zone governs); a stored name that no longer resolves is a **corrupt record**, failing loudly and
naming the key, never silently substituting the deployment zone (ADR-0025 per-rule addendum). The fencing `claim` token and `claimed_at` are adapter mechanics persisted
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
record is raised as the core's `SessionStoreError` (session), `TaskStoreError` (task),
`ScheduleStoreError` (schedule), or `HandoffStoreError` (handoff); backend failures carry the
original exception chained as
`__cause__`, decode failures name the offending record (session: list index + kind/version;
task/schedule/handoff: the key); no `redis.exceptions.*` type ever crosses the port. The one
exception to fail-loud is the schedule **claim path**, where a corrupt record quarantines
(ADR-0025's poison-pill defense) rather than raising.

**Contract tests.** `tests/contract.py` is one shared behavior suite (empty history,
append→history order, multi-session isolation, roundtrip fidelity incl. timezone,
`list_sessions` recency-ordering + title/preview derivation, `set_title` overriding the
first-message title (ADR-0021 titles addendum), the recap verbs (ADR-0038 decision 9), and
pinning: `set_pinned` marking/clearing the
summary idempotently, a pinned chat older than the window escaping recency and sorting above the
recency group, a pinned-and-recent chat not duplicated, and delete clearing the pin, ADR-0021
pinning addendum) run against BOTH implementations (`InMemorySessionStore` and `RedisSessionStore`
over fakeredis) plus fakeredis-injected failure tests for the error wrapping (append, history,
list, `set_title`, `set_pinned`, close, plus a failure inside the batched end-reads) and
Redis-specific edges (`list_sessions` empty store, limit, dangling index entry, a tolerated
corrupt record between the ends, a fatal one at either end named by its true index; a stored
title persisted under its own key and read back truncated; and, over the raw keyspace, the pinned
set holding/dropping its member, the union lifting a pinned old chat past the window, and a
dangling pinned entry skipped; the recap document's shape on the wire, its removal by delete, an
unreadable kind/version, a corrupt document, a document whose fields would build an invalid value,
and connection failures on both recap verbs). The recap checks in the shared suite are its absence
before any write, a full roundtrip and overwrite, per-session isolation, and a read-back after the
write, which on the live-Redis run is a real round trip to another process and so is the one that
means the most: the recap crossing a model swap is exactly that read. The `list_sessions` check filters the global list to the ids it
created, which narrows the read to one row but cannot rescue a check whose fixtures were crowded
out of the window in the first place; that is the live runs' isolated database, below.
`tests/task_contract.py`
does the same for the `TaskStore` (missing→None, task/result round-trip, timezone fidelity) over
`InMemoryTaskStore` and `RedisTaskStore`, plus disconnected/corrupt-record failure tests.
`tests/schedule_contract.py` does it for the `ScheduleStore`. The fenced protocol is the
point of that suite (stale finish rejected, cancel-during-fire sticks, lease-expiry re-claim
under a fresh token, terminal cleanup, fire-time taint OR, delivery lifecycle), and it runs over
`InMemoryScheduleStore` and `RedisScheduleStore`, with adapter-only mechanics (error wrapping
per operation, codec policy, quarantine, dangling-id tolerance, surplus release) tested against
the Redis adapter alone. `tests/handoff_contract.py` does it for the `HandoffStore` over
`InMemoryHandoffStore` and `RedisHandoffStore` (ADR-0030); its load-bearing check is the
tainted-ledger round trip (a ledger built through the real `TaintLedger` API with attested and
claimed sources comes back bit-, order-, and set-exact via `HandoffRecord.taint_ledger()`) with
the `opaque` bit's own both-poles round trip beside it (ADR-0029/0030: a clean record reads back
`False` and an image-marked one `True`, on the record and on the rebuilt ledger, because both of
that bit's consumers open on a `False` after the swap), then the lifecycle checks (active-slot
claim/release across put/transition/delete, terminal records readable but never active,
unknown-id no-ops, timezone fidelity on the record and its tool-bearing tail), with adapter-only
mechanics (error wrapping per operation, strict corrupt-record policy over each of the four taint
fields and a forged provenance kind, terminal-only TTL, dangling/terminal pointer self-healing)
against the Redis adapter alone. The
integration-marked tests in `tests/test_store_live.py`, `tests/test_handoff_live.py`, and
`tests/test_schedule_live.py` run the suites against real Redis
(excluded from CI/coverage by the workspace addopts; run manually:
`cd brain && uv run pytest -m integration --no-cov packages/session`. Here the `--no-cov`
matters, the 100% gate in addopts would otherwise fail the run). All three take their store
from `tests/live_redis.py`, which is the one place that knows how a live run is isolated: it
rewrites `CORTEX_REDIS_URL` onto **its own logical database** (`LIVE_DB`, database 15, which
production never selects) and its `reset` empties that database before the suite and again
after every check, including a check that FAILS. So each check starts from the same empty
store the fakeredis fixture gives it, which is what lets these three suites be the identical
suites the fixture runs rather than hedged versions of them, and no real session, schedule, or
handoff is read, written, or deleted. Two guards keep the flush honest: the URL rewrite refuses
a `CORTEX_REDIS_URL` that already selects `LIVE_DB`, and `reset` re-reads the database its
client actually opened before flushing anything. Nothing about this reaches the adapters, which
keep their key layouts and gained no prefix, namespace, or database argument (ADR-0002 addendum
on the live-run database). This replaces the earlier prefix sweeps, which had to restate each
adapter's key layout inside the test, and the schedule and handoff suites' skips, which reported
green while asserting nothing whenever the shared database held a real record.

**Invariants.**
- State outlives every process: nothing is cached in the adapter; every read hits
  Redis. Two stores (or two orchestrator processes) over the same URL see the same
  sessions.
- The JSON schema above is the persisted contract. Extend, don't repurpose fields.
- Fully typed (PEP 561 `py.typed`); pyright strict clean; 100% line+branch covered by
  the contract suite (the live suite adds no coverage by design).

**Dependencies.** cortex-core (workspace), redis (asyncio client). Dev-only (workspace
root): fakeredis (contract tests without a server).
