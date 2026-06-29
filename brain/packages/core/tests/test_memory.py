"""Behavior of the memory value types, in-memory fakes, and the MemoryRecaller use-case."""

import uuid
from datetime import UTC, datetime

import pytest

from cortex_core import (
    HashEmbedder,
    InMemoryMemoryStore,
    MemoryRecaller,
    MemoryRecord,
)

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


class _FixedClock:
    """A Clock pinned to ``_AT`` so recorded timestamps are assertable."""

    def now(self) -> datetime:
        return _AT


def _record(text: str, embedding: tuple[float, ...], *, record_id: str = "m-1") -> MemoryRecord:
    return MemoryRecord(id=record_id, text=text, embedding=embedding, at=_AT)


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


async def test_record_builds_persists_and_returns_the_memory() -> None:
    store = InMemoryMemoryStore()
    embedder = HashEmbedder()
    recaller = MemoryRecaller(store, embedder, _FixedClock(), id_factory=lambda: "fixed-id")
    stored = await recaller.record("remember this")
    assert stored.id == "fixed-id"
    assert stored.at is _AT
    assert stored.text == "remember this"
    assert stored.embedding == tuple(await embedder.embed("remember this"))
    # It is genuinely in the store: recall of the same text surfaces exactly it.
    (hit,) = await recaller.recall("remember this", k=1)
    assert hit.record == stored


async def test_recall_embeds_the_query_and_returns_the_closest_memory() -> None:
    store = InMemoryMemoryStore()
    ids = iter(["a", "b"])
    recaller = MemoryRecaller(store, HashEmbedder(), _FixedClock(), id_factory=lambda: next(ids))
    await recaller.record("alpha")
    await recaller.record("beta")
    hits = await recaller.recall("alpha", k=2)
    assert len(hits) == 2
    assert hits[0].record.text == "alpha"
    assert hits[0].score == pytest.approx(1.0)


async def test_record_uses_uuid_ids_by_default() -> None:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), _FixedClock())
    stored = await recaller.record("x")
    assert uuid.UUID(stored.id).version == 4  # parses as a v4 uuid → default factory ran
