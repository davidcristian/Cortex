"""Shared MemoryStore behavior checks. Every implementation must satisfy all of them.

Driven by the integration test against real Postgres+pgvector; the in-memory fake is
checked directly in cortex_core's tests. Each check generates unique memory ids (safe
against a shared live DB) and returns them so a live run can clean up after itself.
Embeddings are float4-exact values so the roundtrip check holds against pgvector's storage.
"""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

from cortex_core import MemoryRecord, MemoryStore

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


def _id() -> str:
    return f"contract-{uuid4()}"


def make_record(text: str, embedding: tuple[float, ...], *, at: datetime = _AT) -> MemoryRecord:
    return MemoryRecord(id=_id(), text=text, embedding=embedding, at=at)


async def check_empty_search(store: MemoryStore) -> list[str]:
    """A store with no matching rows returns an empty result, not an error."""
    assert list(await store.search((1.0, 0.0, 0.0), k=5)) == []
    return []


async def check_ranks_by_similarity(store: MemoryStore) -> list[str]:
    """Search returns the most cosine-similar memory first."""
    near = make_record("near", (1.0, 0.0, 0.0))
    far = make_record("far", (0.0, 1.0, 0.0))
    await store.add(far)
    await store.add(near)
    hits = await store.search((1.0, 0.0, 0.0), k=2)
    assert [hit.record.text for hit in hits] == ["near", "far"]
    assert hits[0].score > hits[1].score
    return [near.id, far.id]


async def check_top_k_truncates(store: MemoryStore) -> list[str]:
    """search(k) returns at most k results."""
    records = [make_record(f"m{i}", (float(i + 1), 0.0, 0.0)) for i in range(3)]
    for record in records:
        await store.add(record)
    assert len(await store.search((1.0, 0.0, 0.0), k=1)) == 1
    return [record.id for record in records]


async def check_roundtrip_fidelity(store: MemoryStore) -> list[str]:
    """A stored memory reads back with its fields intact (float4-exact embedding; instant tz)."""
    original = make_record(
        "unicode ✓ / newline\n",
        (1.0, 0.5, -0.25),
        at=datetime(2026, 7, 3, 17, 45, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))),
    )
    await store.add(original)
    (hit,) = await store.search((1.0, 0.5, -0.25), k=1)
    assert hit.record.id == original.id
    assert hit.record.text == original.text
    assert tuple(hit.record.embedding) == original.embedding
    # timestamptz normalizes to UTC, so compare the instant (not the original offset).
    assert hit.record.at == original.at
    return [original.id]


ALL_CHECKS = (
    check_empty_search,
    check_ranks_by_similarity,
    check_top_k_truncates,
    check_roundtrip_fidelity,
)
