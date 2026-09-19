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
    MemoryStoreError,
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
    """A clock fixed at ``_AT`` so recorded timestamps can be compared exactly."""

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
    assert removed == 2
    assert await store.search([1.0, 0.0], k=5, scopes=["conv-a"]) == ()
    kept = await store.search([1.0, 0.0], k=5, scopes=["conv-b"])
    assert [hit.record.id for hit in kept] == ["b1"]


async def test_delete_scope_without_matches_returns_zero() -> None:
    store = InMemoryMemoryStore()
    await store.add(_record("a1", (1.0, 0.0), record_id="a1", scope="conv-a"))
    assert await store.delete_scope("conv-x") == 0
    assert len(await store.search([1.0, 0.0], k=5)) == 1


async def test_a_store_told_to_fail_takes_every_verb_away_the_way_a_lost_backend_does() -> None:
    store = InMemoryMemoryStore()
    await store.add(_record("a1", (1.0, 0.0), record_id="a1", scope="conv-a"))
    store.fail_with(MemoryStoreError("the memory store is unreachable"))

    with pytest.raises(MemoryStoreError, match="unreachable"):
        await store.add(_record("a2", (1.0, 0.0), record_id="a2", scope="conv-a"))
    with pytest.raises(MemoryStoreError, match="unreachable"):
        await store.search([1.0, 0.0], k=5)
    with pytest.raises(MemoryStoreError, match="unreachable"):
        await store.count_candidates()
    with pytest.raises(MemoryStoreError, match="unreachable"):
        await store.delete_scope("conv-a")


def test_the_recaller_exposes_no_forget_verb_so_no_turn_can_delete_memory() -> None:
    # A turn reaches memory only through MemoryRecaller, and memory is in no tool registry, so no
    # tool call can delete anything. If a delete verb is added here, work out the taint path first.
    assert not hasattr(MemoryRecaller, "delete_scope")
    turn_facing = {name for name in vars(MemoryRecaller) if not name.startswith("_")}
    assert turn_facing == {"record", "recall"}


class _SpyDeleteStore(InMemoryMemoryStore):
    """An InMemoryMemoryStore that records every scope passed to ``delete_scope``."""

    def __init__(self) -> None:
        super().__init__()
        self.deleted_scopes: list[str] = []

    async def delete_scope(self, scope: str) -> int:
        self.deleted_scopes.append(scope)
        return await super().delete_scope(scope)


class _FixedBucketScope:
    """A MemoryScope that writes every session to one shared scope of its own."""

    def write_scope(self, session_id: str) -> str:
        del session_id
        return "shared-bucket"

    def read_scopes(self, session_id: str) -> Sequence[str] | None:
        del session_id
        return ("shared-bucket",)


async def test_cascade_forgets_a_session_scoped_chats_own_memories() -> None:
    store = _SpyDeleteStore()
    await store.add(_record("chat-a fact", (1.0, 0.0), record_id="a1", scope="chat-a"))
    await store.add(_record("chat-a fact 2", (1.0, 0.0), record_id="a2", scope="chat-a"))
    await store.add(_record("chat-b fact", (1.0, 0.0), record_id="b1", scope="chat-b"))
    cascade = SessionMemoryCascade(store, SessionMemoryScope())
    removed = await cascade.delete_session_memories("chat-a")
    assert removed == 2
    assert store.deleted_scopes == ["chat-a"]
    assert await store.search([1.0, 0.0], k=5, scopes=["chat-a"]) == ()
    kept = await store.search([1.0, 0.0], k=5, scopes=["chat-b"])
    assert [hit.record.id for hit in kept] == ["b1"]


async def test_cascade_does_not_run_under_global_scoping() -> None:
    store = _SpyDeleteStore()
    await store.add(_record("a shared fact", (1.0, 0.0), record_id="g1", scope=GLOBAL_SCOPE))
    cascade = SessionMemoryCascade(store, GlobalMemoryScope())
    removed = await cascade.delete_session_memories("any-session")
    assert removed == 0
    assert store.deleted_scopes == []
    survived = await store.search([1.0, 0.0], k=5)
    assert [hit.record.id for hit in survived] == ["g1"]


async def test_cascade_never_passes_global_scope_even_for_a_session_named_global() -> None:
    store = _SpyDeleteStore()
    await store.add(_record("a shared fact", (1.0, 0.0), record_id="g1", scope=GLOBAL_SCOPE))
    cascade = SessionMemoryCascade(store, SessionMemoryScope())
    removed = await cascade.delete_session_memories(GLOBAL_SCOPE)
    assert removed == 0
    assert store.deleted_scopes == []
    survived = await store.search([1.0, 0.0], k=5)
    assert [hit.record.id for hit in survived] == ["g1"]


async def test_cascade_refuses_a_shared_bucket_that_is_not_the_session_scope() -> None:
    store = _SpyDeleteStore()
    await store.add(_record("bucket fact", (1.0, 0.0), record_id="k1", scope="shared-bucket"))
    cascade = SessionMemoryCascade(store, _FixedBucketScope())
    removed = await cascade.delete_session_memories("some-session")
    assert removed == 0
    assert store.deleted_scopes == []
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
    assert stored.scope == GLOBAL_SCOPE
    assert stored.tainted is False
    (hit,) = await recaller.recall("remember this", k=1, session_id="s", turn_id="t")
    assert hit.record == stored


async def test_record_stamps_the_tainted_marker_when_requested() -> None:
    store = InMemoryMemoryStore()
    recaller = MemoryRecaller(store, HashEmbedder(), _FixedClock(), id_factory=lambda: "t-mem")
    stored = await recaller.record("from a hostile file", session_id="s", tainted=True)
    assert stored.tainted is True
    (hit,) = await recaller.recall("from a hostile file", k=1, session_id="s", turn_id="t")
    assert hit.record.tainted is True


async def test_recall_embeds_the_query_and_returns_the_closest_memory() -> None:
    store = InMemoryMemoryStore()
    ids = iter(["a", "b"])
    recaller = MemoryRecaller(store, HashEmbedder(), _FixedClock(), id_factory=lambda: next(ids))
    await recaller.record("alpha", session_id="s")
    await recaller.record("beta", session_id="s")
    hits = await recaller.recall("alpha", k=2, session_id="s", turn_id="t")
    assert len(hits) == 2
    assert hits[0].record.text == "alpha"
    assert hits[0].score == pytest.approx(1.0)


async def test_record_uses_uuid_ids_by_default() -> None:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), _FixedClock())
    stored = await recaller.record("x", session_id="s")
    assert uuid.UUID(stored.id).version == 4


def test_memory_record_defaults_to_the_global_scope() -> None:
    assert _record("hi", (1.0, 0.0)).scope == GLOBAL_SCOPE
    assert MemoryRecord(id="m", text="t", embedding=(1.0,), at=_AT, scope="work").scope == "work"


def test_memory_record_defaults_to_untainted() -> None:
    assert _record("hi", (1.0, 0.0)).tainted is False
    tainted = MemoryRecord(id="m", text="t", embedding=(1.0,), at=_AT, tainted=True)
    assert tainted.tainted is True


def test_global_memory_scope_writes_global_and_reads_everything() -> None:
    scope = GlobalMemoryScope()
    assert scope.write_scope("session-a") == GLOBAL_SCOPE
    assert scope.read_scopes("session-a") is None
    assert GLOBAL_MEMORY_SCOPE.read_scopes("session-a") is None


def test_session_memory_scope_isolates_by_session() -> None:
    scope = SessionMemoryScope()
    assert scope.write_scope("session-a") == "session-a"
    assert scope.read_scopes("session-a") == ("session-a",)


async def test_scoped_search_filters_the_candidate_set() -> None:
    store = InMemoryMemoryStore()
    await store.add(_record("a-mem", (1.0, 0.0), record_id="a", scope="scope-a"))
    await store.add(_record("b-mem", (1.0, 0.0), record_id="b", scope="scope-b"))
    only_a = await store.search([1.0, 0.0], k=5, scopes=["scope-a"])
    assert [hit.record.id for hit in only_a] == ["a"]
    both = await store.search([1.0, 0.0], k=5, scopes=["scope-a", "scope-b"])
    assert {hit.record.id for hit in both} == {"a", "b"}
    unfiltered = await store.search([1.0, 0.0], k=5)
    assert {hit.record.id for hit in unfiltered} == {"a", "b"}


class _SpyRecallPolicy:
    """A RecallPolicy that records how the recaller called it and keeps only the first hit."""

    def __init__(self) -> None:
        self.select_call: tuple[tuple[str, ...], str, datetime, int] | None = None
        self.session_id: str | None = None
        self.turn_id: str | None = None

    def candidate_k(self, k: int) -> int:
        return k + 3

    async def select(
        self,
        hits: Sequence[ScoredMemory],
        *,
        query: str,
        now: datetime,
        k: int,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> Ranking:
        self.select_call = (tuple(hit.record.id for hit in hits), query, now, k)
        self.session_id = session_id
        self.turn_id = turn_id
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
    hits = await recaller.recall("fact 0", k=2, session_id="s", turn_id="t")
    assert spy.select_call is not None
    pool_ids, query, now, k = spy.select_call
    assert len(pool_ids) == 5
    assert query == "fact 0"
    assert now == _AT
    assert k == 2
    assert len(hits) == 1


async def test_the_policy_is_told_which_recall_it_is_ranking() -> None:
    spy = _SpyRecallPolicy()
    recaller = MemoryRecaller(
        InMemoryMemoryStore(), HashEmbedder(), _FixedClock(), policy=spy, id_factory=lambda: "m0"
    )
    await recaller.record("a fact", session_id="the-writer")

    await recaller.recall("a fact", k=1, session_id="the-reader", turn_id="the-turn")

    assert spy.session_id == "the-reader"
    assert spy.turn_id == "the-turn"


async def test_recall_audits_the_ranking_when_a_sink_is_wired() -> None:
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
    await recaller.recall("fact 0", k=1, session_id="s", turn_id="the-turn")
    (audit,) = sink.audits
    assert audit.session_id == "s"
    assert audit.turn_id == "the-turn"
    assert audit.query == "fact 0"
    assert audit.k == 1
    assert audit.pool_size == 3
    assert audit.at == _AT
    assert audit.ranking.basis is RankBasis.VERDICT
    assert [ranked.hit.record.id for ranked in audit.ranking.hits] == ["m0"]


async def test_the_trail_says_how_many_candidates_there_were_not_only_how_many_came_back() -> None:
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
    await recaller.recall("fact 0", k=1, session_id="s", turn_id="t")

    (audit,) = sink.audits
    assert audit.pool_size == 4
    assert audit.available == 9


async def test_the_counted_candidates_are_the_read_scopes_and_not_the_whole_store() -> None:
    store = InMemoryMemoryStore()
    sink = RecordingRecallSink()
    recaller = MemoryRecaller(
        store, HashEmbedder(), _FixedClock(), scope=SessionMemoryScope(), audit=sink
    )
    for i in range(4):
        await recaller.record(f"fact {i}", session_id="conv-a")
    await recaller.record("only one here", session_id="conv-b")

    await recaller.recall("fact 0", k=5, session_id="conv-b", turn_id="t")

    (audit,) = sink.audits
    assert audit.available == 1


class _DecliningRecallPolicy:
    """A RecallPolicy that reads the pool and keeps none of it, as a declining judge does."""

    def candidate_k(self, k: int) -> int:
        return k

    async def select(
        self,
        hits: Sequence[ScoredMemory],
        *,
        query: str,
        now: datetime,
        k: int,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> Ranking:
        del hits, query, now, k, session_id, turn_id
        return Ranking(hits=(), basis=RankBasis.DEMUR)


async def test_a_declined_rank_reaches_the_turn_as_no_memories_and_the_trail_says_why() -> None:
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

    assert await recaller.recall("a fact", k=3, session_id="s", turn_id="t") == ()

    (audit,) = sink.audits
    assert audit.pool_size == 1
    assert audit.ranking.hits == ()
    assert audit.ranking.basis is RankBasis.DEMUR


async def test_the_trail_names_the_candidates_the_policy_left_behind() -> None:
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
    await recaller.recall("fact 0", k=1, session_id="s", turn_id="t")

    pool = await store.search(await HashEmbedder().embed("fact 0"), k=3)
    (audit,) = sink.audits
    assert [ranked.hit.record.id for ranked in audit.ranking.hits] == [pool[0].record.id]
    assert [(hit.record.id, hit.score) for hit in pool[1:]] == [
        (candidate.id, candidate.score) for candidate in audit.dropped.carried
    ]
    assert audit.dropped.omitted == 0


async def test_recall_without_a_sink_records_nothing() -> None:
    store = InMemoryMemoryStore()
    recaller = MemoryRecaller(store, HashEmbedder(), _FixedClock(), id_factory=lambda: "m0")
    await recaller.record("a fact", session_id="s")
    assert len(await recaller.recall("a fact", k=1, session_id="s", turn_id="t")) == 1


class _CountingPool(list[ScoredMemory]):
    """A pool that counts how many times it is read end to end."""

    def __init__(self, hits: Sequence[ScoredMemory]) -> None:
        super().__init__(hits)
        self.walks = 0

    def __iter__(self) -> Iterator[ScoredMemory]:
        self.walks += 1
        return super().__iter__()


_READ_ONLY = "this store only ever serves its one pool"


class _PoolStore:
    """A MemoryStore that returns the one counted pool it was built with from every search."""

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
        return len(self.pool)

    async def delete_scope(self, scope: str) -> int:
        del scope
        raise AssertionError(_READ_ONLY)


async def _reads_recalling(*, audited: bool) -> tuple[int, int]:
    """What one recall costs the store, with and without the trail: pool reads, then counts."""
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
    await recaller.recall("a fact", k=1, session_id="s", turn_id="t")
    return pool.walks, store.counts


async def test_the_silent_path_assembles_no_record_for_a_sink_that_is_not_there() -> None:
    assert await _reads_recalling(audited=False) == (1, 0)
    assert await _reads_recalling(audited=True) == (2, 1)


async def test_session_scoped_recaller_does_not_cross_conversations() -> None:
    store = InMemoryMemoryStore()
    recaller = MemoryRecaller(store, HashEmbedder(), _FixedClock(), scope=SessionMemoryScope())
    await recaller.record("secret from A", session_id="conv-a")
    assert await recaller.recall("secret from A", k=5, session_id="conv-b", turn_id="t") == ()
    (hit,) = await recaller.recall("secret from A", k=5, session_id="conv-a", turn_id="t")
    assert hit.record.text == "secret from A"
    assert hit.record.scope == "conv-a"
