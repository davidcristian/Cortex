"""Behavior of the memory value types, in-memory fakes, and the MemoryRecaller use-case."""

import uuid
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    GLOBAL_MEMORY_SCOPE,
    GLOBAL_SCOPE,
    GlobalMemoryScope,
    HashEmbedder,
    InMemoryMemoryStore,
    MemoryRecaller,
    MemoryRecord,
    RankBasis,
    RankedMemory,
    Ranking,
    RecordingRecallSink,
    ScoredMemory,
    SessionMemoryCascade,
    SessionMemoryScope,
)

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


class _FixedClock:
    """A Clock pinned to ``_AT`` so recorded timestamps are assertable."""

    def now(self) -> datetime:
        return _AT


def _record(
    text: str, embedding: tuple[float, ...], *, record_id: str = "m-1", scope: str = GLOBAL_SCOPE
) -> MemoryRecord:
    return MemoryRecord(id=record_id, text=text, embedding=embedding, at=_AT, scope=scope)


def test_memory_record_rejects_a_naive_timestamp() -> None:
    naive = datetime(2026, 7, 3, 12, 0, 0)  # noqa: DTZ001 - deliberately naive for the check
    with pytest.raises(ValueError, match="timezone-aware"):
        MemoryRecord(id="m-1", text="hi", embedding=(1.0,), at=naive)


def test_memory_record_keeps_an_aware_timestamp() -> None:
    record = _record("hi", (1.0, 0.0))
    assert record.at is _AT
    assert record.embedding == (1.0, 0.0)


async def test_hash_embedder_is_deterministic() -> None:
    embedder = HashEmbedder()
    assert list(await embedder.embed("alpha")) == list(await embedder.embed("alpha"))


async def test_hash_embedder_separates_distinct_text() -> None:
    embedder = HashEmbedder()
    assert await embedder.embed("alpha") != await embedder.embed("beta")


async def test_hash_embedder_honors_the_requested_dimension() -> None:
    assert len(await HashEmbedder(dimension=32).embed("alpha")) == 32
    assert len(await HashEmbedder().embed("alpha")) == 16


async def test_empty_store_search_returns_nothing() -> None:
    assert await InMemoryMemoryStore().search([1.0, 0.0], k=5) == ()


async def test_search_ranks_by_cosine_similarity_most_similar_first() -> None:
    store = InMemoryMemoryStore()
    near = _record("near", (1.0, 0.0), record_id="near")
    far = _record("far", (0.0, 1.0), record_id="far")
    await store.add(far)
    await store.add(near)
    hits = await store.search([1.0, 0.0], k=2)
    assert [hit.record.id for hit in hits] == ["near", "far"]
    assert hits[0].score == pytest.approx(1.0)
    assert hits[1].score == 0.0


async def test_search_truncates_to_k() -> None:
    store = InMemoryMemoryStore()
    for i in range(3):
        await store.add(_record(f"m{i}", (float(i + 1), 0.0), record_id=f"m{i}"))
    assert len(await store.search([1.0, 0.0], k=1)) == 1


async def test_a_zero_vector_memory_scores_zero_and_ranks_last() -> None:
    store = InMemoryMemoryStore()
    real = _record("real", (1.0, 0.0), record_id="real")
    degenerate = _record("degenerate", (0.0, 0.0), record_id="degenerate")
    await store.add(degenerate)
    await store.add(real)
    hits = await store.search([1.0, 0.0], k=2)
    assert [hit.record.id for hit in hits] == ["real", "degenerate"]
    assert hits[1].score == 0.0


async def test_delete_scope_removes_only_its_namespace_and_counts() -> None:
    store = InMemoryMemoryStore()
    await store.add(_record("a1", (1.0, 0.0), record_id="a1", scope="conv-a"))
    await store.add(_record("a2", (1.0, 0.0), record_id="a2", scope="conv-a"))
    await store.add(_record("b1", (1.0, 0.0), record_id="b1", scope="conv-b"))
    removed = await store.delete_scope("conv-a")
    assert removed == 2  # both conv-a memories, and only those
    assert await store.search([1.0, 0.0], k=5, scopes=["conv-a"]) == ()  # the scope is empty now
    kept = await store.search([1.0, 0.0], k=5, scopes=["conv-b"])
    assert [hit.record.id for hit in kept] == ["b1"]  # conv-b survives


async def test_delete_scope_without_matches_returns_zero() -> None:
    store = InMemoryMemoryStore()
    await store.add(_record("a1", (1.0, 0.0), record_id="a1", scope="conv-a"))
    assert await store.delete_scope("conv-x") == 0  # nothing matched, no error
    assert len(await store.search([1.0, 0.0], k=5)) == 1  # the store is untouched


def test_the_recaller_exposes_no_forget_verb_so_no_turn_can_delete_memory() -> None:
    # Data-loss safety for the new delete verb (ADR-0008 delete-scope addendum). ``delete_scope``
    # lives on the ``MemoryStore`` port for out-of-band trusted callers (a session-delete cascade,
    # an eviction policy). A turn reaches memory only through the ``MemoryRecaller`` handed to the
    # engine as ``caps.memory``, which exposes record/recall and nothing else, and memory is not a
    # tool in any registry, so no tool call, tainted or not, can spell "forget everything". If a
    # delete method is ever added here, this reddens so the taint path is reconsidered first.
    assert not hasattr(MemoryRecaller, "delete_scope")
    turn_facing = {name for name in vars(MemoryRecaller) if not name.startswith("_")}
    assert turn_facing == {"record", "recall"}


class _SpyDeleteStore(InMemoryMemoryStore):
    """An InMemoryMemoryStore that records every scope handed to ``delete_scope``.

    Lets a cascade test prove not just the returned count but that ``GLOBAL_SCOPE`` is NEVER passed
    at all, an invariant a bare "returns 0" could hide if the guard deleted a namespace that
    happened to hold nothing.
    """

    def __init__(self) -> None:
        super().__init__()
        self.deleted_scopes: list[str] = []

    async def delete_scope(self, scope: str) -> int:
        self.deleted_scopes.append(scope)
        return await super().delete_scope(scope)


class _FixedBucketScope:
    """A MemoryScope writing every session to one shared bucket (neither global nor per-session).

    Proves the cascade refuses a scope that is not the session's own private space even when it is
    not ``GLOBAL_SCOPE`` (the ``scope != session_id`` guard branch).
    """

    def write_scope(self, session_id: str) -> str:
        del session_id
        return "shared-bucket"

    def read_scopes(self, session_id: str) -> Sequence[str] | None:
        del session_id
        return ("shared-bucket",)


async def test_cascade_forgets_a_session_scoped_chats_own_memories() -> None:
    """Under session scoping the cascade deletes exactly the chat's own namespace and counts it."""
    store = _SpyDeleteStore()
    await store.add(_record("chat-a fact", (1.0, 0.0), record_id="a1", scope="chat-a"))
    await store.add(_record("chat-a fact 2", (1.0, 0.0), record_id="a2", scope="chat-a"))
    await store.add(_record("chat-b fact", (1.0, 0.0), record_id="b1", scope="chat-b"))
    cascade = SessionMemoryCascade(store, SessionMemoryScope())
    removed = await cascade.delete_session_memories("chat-a")
    assert removed == 2  # both of chat-a's private memories
    assert store.deleted_scopes == ["chat-a"]  # its own scope, and only it
    assert await store.search([1.0, 0.0], k=5, scopes=["chat-a"]) == ()  # gone
    kept = await store.search([1.0, 0.0], k=5, scopes=["chat-b"])
    assert [hit.record.id for hit in kept] == ["b1"]  # another chat is untouched


async def test_cascade_does_not_run_under_global_scoping() -> None:
    """THE critical guard: under the shared global space nothing session-private cascades, and
    ``GLOBAL_SCOPE`` is NEVER handed to ``delete_scope`` (which would erase every conversation)."""
    store = _SpyDeleteStore()
    await store.add(_record("a shared fact", (1.0, 0.0), record_id="g1", scope=GLOBAL_SCOPE))
    cascade = SessionMemoryCascade(store, GlobalMemoryScope())
    removed = await cascade.delete_session_memories("any-session")
    assert removed == 0  # nothing session-private to forget
    assert store.deleted_scopes == []  # delete_scope never called: GLOBAL_SCOPE never passed
    survived = await store.search([1.0, 0.0], k=5)  # the shared space is fully intact
    assert [hit.record.id for hit in survived] == ["g1"]


async def test_cascade_never_passes_global_scope_even_for_a_session_named_global() -> None:
    """A session whose id EQUALS ``GLOBAL_SCOPE`` under SESSION scoping still cannot sweep the
    shared space: the ``GLOBAL_SCOPE`` guard is checked first, so ``write_scope == GLOBAL_SCOPE``
    is refused before the ``scope == session_id`` test could ever admit it."""
    store = _SpyDeleteStore()
    await store.add(_record("a shared fact", (1.0, 0.0), record_id="g1", scope=GLOBAL_SCOPE))
    cascade = SessionMemoryCascade(store, SessionMemoryScope())
    removed = await cascade.delete_session_memories(GLOBAL_SCOPE)  # a session id of "global"
    assert removed == 0
    assert store.deleted_scopes == []  # GLOBAL_SCOPE never reached delete_scope
    survived = await store.search([1.0, 0.0], k=5)
    assert [hit.record.id for hit in survived] == ["g1"]  # the shared space survives


async def test_cascade_refuses_a_shared_bucket_that_is_not_the_session_scope() -> None:
    """A policy writing to a shared bucket (not global, not the session's own scope) is not swept:
    the cascade runs only when the write scope IS the session id (``scope != session_id``)."""
    store = _SpyDeleteStore()
    await store.add(_record("bucket fact", (1.0, 0.0), record_id="k1", scope="shared-bucket"))
    cascade = SessionMemoryCascade(store, _FixedBucketScope())
    removed = await cascade.delete_session_memories("some-session")
    assert removed == 0
    assert store.deleted_scopes == []  # a shared-but-not-global bucket is left intact
    assert len(await store.search([1.0, 0.0], k=5)) == 1


async def test_record_builds_persists_and_returns_the_memory() -> None:
    store = InMemoryMemoryStore()
    embedder = HashEmbedder()
    recaller = MemoryRecaller(store, embedder, _FixedClock(), id_factory=lambda: "fixed-id")
    stored = await recaller.record("remember this", session_id="s")
    assert stored.id == "fixed-id"
    assert stored.at is _AT
    assert stored.text == "remember this"
    assert stored.embedding == tuple(await embedder.embed("remember this"))
    assert stored.scope == GLOBAL_SCOPE  # the default policy writes the global space
    assert stored.tainted is False  # an untainted turn writes a trusted memory (ADR-0019)
    # It is genuinely in the store: recall of the same text surfaces exactly it.
    (hit,) = await recaller.recall("remember this", k=1, session_id="s")
    assert hit.record == stored


async def test_record_stamps_the_tainted_marker_when_requested() -> None:
    # A tainted turn records its exchange with the untrusted-provenance marker so recall can
    # fence it (ADR-0019); the recaller only carries the flag onto the record.
    store = InMemoryMemoryStore()
    recaller = MemoryRecaller(store, HashEmbedder(), _FixedClock(), id_factory=lambda: "t-mem")
    stored = await recaller.record("from a hostile file", session_id="s", tainted=True)
    assert stored.tainted is True
    (hit,) = await recaller.recall("from a hostile file", k=1, session_id="s")
    assert hit.record.tainted is True


async def test_recall_embeds_the_query_and_returns_the_closest_memory() -> None:
    store = InMemoryMemoryStore()
    ids = iter(["a", "b"])
    recaller = MemoryRecaller(store, HashEmbedder(), _FixedClock(), id_factory=lambda: next(ids))
    await recaller.record("alpha", session_id="s")
    await recaller.record("beta", session_id="s")
    hits = await recaller.recall("alpha", k=2, session_id="s")
    assert len(hits) == 2
    assert hits[0].record.text == "alpha"
    assert hits[0].score == pytest.approx(1.0)


async def test_record_uses_uuid_ids_by_default() -> None:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), _FixedClock())
    stored = await recaller.record("x", session_id="s")
    assert uuid.UUID(stored.id).version == 4  # parses as a v4 uuid → default factory ran


def test_memory_record_defaults_to_the_global_scope() -> None:
    assert _record("hi", (1.0, 0.0)).scope == GLOBAL_SCOPE
    assert MemoryRecord(id="m", text="t", embedding=(1.0,), at=_AT, scope="work").scope == "work"


def test_memory_record_defaults_to_untainted() -> None:
    assert _record("hi", (1.0, 0.0)).tainted is False  # trusted provenance unless marked (ADR-0019)
    tainted = MemoryRecord(id="m", text="t", embedding=(1.0,), at=_AT, tainted=True)
    assert tainted.tainted is True


def test_global_memory_scope_writes_global_and_reads_everything() -> None:
    scope = GlobalMemoryScope()
    assert scope.write_scope("session-a") == GLOBAL_SCOPE  # ignores the session
    assert scope.read_scopes("session-a") is None  # no filter, so recall spans all memories
    assert GLOBAL_MEMORY_SCOPE.read_scopes("session-a") is None  # the shared singleton agrees


def test_session_memory_scope_isolates_by_session() -> None:
    scope = SessionMemoryScope()
    assert scope.write_scope("session-a") == "session-a"
    assert scope.read_scopes("session-a") == ("session-a",)


async def test_scoped_search_filters_the_candidate_set() -> None:
    store = InMemoryMemoryStore()
    await store.add(_record("a-mem", (1.0, 0.0), record_id="a", scope="scope-a"))
    await store.add(_record("b-mem", (1.0, 0.0), record_id="b", scope="scope-b"))
    only_a = await store.search([1.0, 0.0], k=5, scopes=["scope-a"])
    assert [hit.record.id for hit in only_a] == ["a"]  # scope-b filtered out
    both = await store.search([1.0, 0.0], k=5, scopes=["scope-a", "scope-b"])
    assert {hit.record.id for hit in both} == {"a", "b"}  # a union of scopes
    unfiltered = await store.search([1.0, 0.0], k=5)
    assert {hit.record.id for hit in unfiltered} == {"a", "b"}  # None spans every scope


class _SpyRecallPolicy:
    """A RecallPolicy that records how the recaller called it and returns only the first hit."""

    def __init__(self) -> None:
        self.select_call: tuple[tuple[str, ...], str, datetime, int] | None = None

    def candidate_k(self, k: int) -> int:
        return k + 3  # ask for a wider pool than the caller's k, to observe the over-fetch

    async def select(
        self, hits: Sequence[ScoredMemory], *, query: str, now: datetime, k: int
    ) -> Ranking:
        self.select_call = (tuple(hit.record.id for hit in hits), query, now, k)
        return Ranking(
            hits=tuple(RankedMemory(hit=hit, key=hit.score) for hit in hits[:1]),
            basis=RankBasis.VERDICT,
        )


async def test_recall_over_fetches_the_pool_and_applies_the_policy() -> None:
    store = InMemoryMemoryStore()
    ids = iter([f"m{i}" for i in range(5)])
    spy = _SpyRecallPolicy()
    recaller = MemoryRecaller(
        store, HashEmbedder(), _FixedClock(), policy=spy, id_factory=lambda: next(ids)
    )
    for i in range(5):
        await recaller.record(f"fact {i}", session_id="s")
    hits = await recaller.recall("fact 0", k=2, session_id="s")
    assert spy.select_call is not None
    pool_ids, query, now, k = spy.select_call
    assert len(pool_ids) == 5  # candidate_k(2) == 5, so the store handed the policy 5 candidates
    assert query == "fact 0"  # the query reaches the policy, which is what a model rank needs
    assert now == _AT  # the recaller passes clock.now() as the recall time
    assert k == 2
    assert len(hits) == 1  # the recaller returns exactly what the policy selected


async def test_recall_audits_the_ranking_when_a_sink_is_wired() -> None:
    """The trail the relevance-field decline had to write a throwaway script for (ADR-0038)."""
    store = InMemoryMemoryStore()
    sink = RecordingRecallSink()
    ids = iter([f"m{i}" for i in range(3)])
    recaller = MemoryRecaller(
        store,
        HashEmbedder(),
        _FixedClock(),
        policy=_SpyRecallPolicy(),
        audit=sink,
        id_factory=lambda: next(ids),
    )
    for i in range(3):
        await recaller.record(f"fact {i}", session_id="s")
    await recaller.recall("fact 0", k=1, session_id="s")
    (audit,) = sink.audits
    assert audit.session_id == "s"
    assert audit.query == "fact 0"
    assert audit.k == 1
    assert audit.pool_size == 3  # the whole pool the policy chose from, not just what it kept
    assert audit.at == _AT
    assert audit.ranking.basis is RankBasis.VERDICT  # the basis that actually ranked
    assert [ranked.hit.record.id for ranked in audit.ranking.hits] == ["m0"]


async def test_the_trail_says_how_many_candidates_there_were_not_only_how_many_came_back() -> None:
    """A pool at its requested width and a store that held exactly that many are two events.

    Nine memories, a pool of four: the numbers must differ, because equal ones are the line's way
    of saying the pool WAS the whole readable store and an id on neither list was never written.
    An `available` measured off the pool would report the cutoff back to itself and read equal
    here (ADR-0038 candidate-count addendum).
    """
    store = InMemoryMemoryStore()
    sink = RecordingRecallSink()
    ids = iter([f"m{i}" for i in range(9)])
    recaller = MemoryRecaller(
        store,
        HashEmbedder(),
        _FixedClock(),
        policy=_SpyRecallPolicy(),
        audit=sink,
        id_factory=lambda: next(ids),
    )
    for i in range(9):
        await recaller.record(f"fact {i}", session_id="s")
    await recaller.recall("fact 0", k=1, session_id="s")

    (audit,) = sink.audits
    assert audit.pool_size == 4  # candidate_k(1), the width the policy asked the store for
    assert audit.available == 9  # and what the store had to offer it, which nothing else reports


async def test_the_counted_candidates_are_the_read_scopes_and_not_the_whole_store() -> None:
    """The count means nothing unless it counts the same set the search ranked over.

    Under session scoping, a recall in one conversation must not be told that the other
    conversation's memories were available to it: they were never candidates.
    """
    store = InMemoryMemoryStore()
    sink = RecordingRecallSink()
    recaller = MemoryRecaller(
        store, HashEmbedder(), _FixedClock(), scope=SessionMemoryScope(), audit=sink
    )
    for i in range(4):
        await recaller.record(f"fact {i}", session_id="conv-a")
    await recaller.record("only one here", session_id="conv-b")

    await recaller.recall("fact 0", k=5, session_id="conv-b")

    (audit,) = sink.audits
    assert audit.available == 1  # conv-b's own namespace, not the five memories the store holds


class _DecliningRecallPolicy:
    """A RecallPolicy that reads the pool and keeps none of it, the judge's refusal in a fake."""

    def candidate_k(self, k: int) -> int:
        return k

    async def select(
        self, hits: Sequence[ScoredMemory], *, query: str, now: datetime, k: int
    ) -> Ranking:
        del hits, query, now, k
        return Ranking(hits=(), basis=RankBasis.DEMUR)


async def test_a_declined_rank_reaches_the_turn_as_no_memories_and_the_trail_says_why() -> None:
    """The recaller does not overrule a policy that kept nothing (ADR-0038 abstention addendum).

    The store holds a matching memory, so the pool is not empty; the policy declines it, and both
    the turn's hits and the audited ranking must say so rather than falling back to the pool.
    """
    store = InMemoryMemoryStore()
    sink = RecordingRecallSink()
    recaller = MemoryRecaller(
        store,
        HashEmbedder(),
        _FixedClock(),
        policy=_DecliningRecallPolicy(),
        audit=sink,
        id_factory=lambda: "m0",
    )
    await recaller.record("a fact", session_id="s")

    assert await recaller.recall("a fact", k=3, session_id="s") == ()

    (audit,) = sink.audits
    assert audit.pool_size == 1  # there WAS something to rank, which is what makes this a refusal
    assert audit.ranking.hits == ()
    assert audit.ranking.basis is RankBasis.DEMUR


async def test_the_trail_names_the_candidates_the_policy_left_behind() -> None:
    """The pool the caller never sees, by id and by the store's own score (ADR-0038 addendum).

    The recaller is the only place that holds both the pool and the ranking, so this is where the
    difference between them is taken. The expectation is read back off the store rather than
    written down, which is what makes "the store's cosine, unchanged" an assertion.
    """
    store = InMemoryMemoryStore()
    sink = RecordingRecallSink()
    ids = iter([f"m{i}" for i in range(3)])
    recaller = MemoryRecaller(
        store,
        HashEmbedder(),
        _FixedClock(),
        policy=_SpyRecallPolicy(),
        audit=sink,
        id_factory=lambda: next(ids),
    )
    for i in range(3):
        await recaller.record(f"fact {i}", session_id="s")
    await recaller.recall("fact 0", k=1, session_id="s")

    pool = await store.search(await HashEmbedder().embed("fact 0"), k=3)
    (audit,) = sink.audits
    assert [ranked.hit.record.id for ranked in audit.ranking.hits] == [pool[0].record.id]
    assert [(hit.record.id, hit.score) for hit in pool[1:]] == [
        (candidate.id, candidate.score) for candidate in audit.dropped.carried
    ]
    assert audit.dropped.omitted == 0  # three candidates is nowhere near the bound


async def test_recall_without_a_sink_records_nothing() -> None:
    """The founding silent path: an unwired audit is not an empty trail, it is no trail."""
    store = InMemoryMemoryStore()
    recaller = MemoryRecaller(store, HashEmbedder(), _FixedClock(), id_factory=lambda: "m0")
    await recaller.record("a fact", session_id="s")
    assert len(await recaller.recall("a fact", k=1, session_id="s")) == 1


class _CountingPool(list[ScoredMemory]):
    """A pool that counts how many times it is walked end to end."""

    def __init__(self, hits: Sequence[ScoredMemory]) -> None:
        super().__init__(hits)
        self.walks = 0

    def __iter__(self) -> Iterator[ScoredMemory]:
        self.walks += 1
        return super().__iter__()


_READ_ONLY = "this store only ever serves its one pool"


class _PoolStore:
    """A MemoryStore that hands every search the one instrumented pool it was built with."""

    def __init__(self, pool: _CountingPool) -> None:
        self.pool = pool
        self.counts = 0

    async def add(self, record: MemoryRecord) -> None:
        del record
        raise AssertionError(_READ_ONLY)

    async def search(
        self, embedding: Sequence[float], *, k: int, scopes: Sequence[str] | None = None
    ) -> Sequence[ScoredMemory]:
        del embedding, k, scopes
        return self.pool

    async def count_candidates(self, *, scopes: Sequence[str] | None = None) -> int:
        del scopes
        self.counts += 1
        return len(self.pool)  # len() does not iterate, so answering costs the pool no walk

    async def delete_scope(self, scope: str) -> int:
        del scope
        raise AssertionError(_READ_ONLY)


async def _reads_recalling(*, audited: bool) -> tuple[int, int]:
    """What one recall costs the store, trail on and off: pool walks, then counting queries."""
    pool = _CountingPool(
        [
            ScoredMemory(
                record=_record("a fact", (1.0, 0.0), record_id=f"m{i}"), score=0.9 - i / 10
            )
            for i in range(3)
        ]
    )
    store = _PoolStore(pool)
    recaller = MemoryRecaller(
        store,
        HashEmbedder(),
        _FixedClock(),
        policy=_SpyRecallPolicy(),
        audit=RecordingRecallSink() if audited else None,
    )
    await recaller.recall("a fact", k=1, session_id="s")
    return pool.walks, store.counts


async def test_the_silent_path_assembles_no_record_for_a_sink_that_is_not_there() -> None:
    """The trail is opt in and costs nothing off, which a widened record could quietly undo.

    The whole audit, including the difference between the pool and the ranking, is built inside
    the "is there a sink" guard. So the unaudited recall walks the pool once, for the policy, and
    the audited one walks it exactly once more. The store's own count of the candidate set is
    inside the same guard and is the one read here that reaches a database (ADR-0038
    candidate-count addendum), so a silent recall must issue none of them at all: no assertion
    about a logged value can catch a query run for a reader who is not there.
    """
    assert await _reads_recalling(audited=False) == (1, 0)
    assert await _reads_recalling(audited=True) == (2, 1)


async def test_session_scoped_recaller_does_not_cross_conversations() -> None:
    store = InMemoryMemoryStore()
    recaller = MemoryRecaller(store, HashEmbedder(), _FixedClock(), scope=SessionMemoryScope())
    await recaller.record("secret from A", session_id="conv-a")
    # Conversation B recalls the same text but must not see A's memory.
    assert await recaller.recall("secret from A", k=5, session_id="conv-b") == ()
    (hit,) = await recaller.recall("secret from A", k=5, session_id="conv-a")
    assert hit.record.text == "secret from A"
    assert hit.record.scope == "conv-a"
