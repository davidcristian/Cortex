"""Shared MemoryStore behavior checks. Every implementation must satisfy all of them.

Driven by the integration test against real Postgres+pgvector; the in-memory fake is
checked directly in cortex_core's tests. Every check assumes an empty store, which the live run
grants it by owning its database and emptying it per check (tests/live_postgres.py) and the fake
grants it by construction, so both run the identical suite. Ids stay unique per check anyway
(the table's primary key). Embeddings are float4-exact values so the roundtrip check holds
against pgvector's storage.
"""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

from cortex_core import GLOBAL_SCOPE, MemoryRecord, MemoryStore

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)

# More memories than the widest pool a shipped deployment over-fetches (``DEFAULT_RECALL_K`` 5 at
# ``CORTEX_MEMORY_RECALL_POOL_FACTOR`` 4), so that a ``count_candidates`` which stops at any cutoff
# a search would have applied is over-counted here rather than agreeing by luck. Sized from what
# ships for the same reason ``DROPPED_TRAIL_LIMIT`` is, and it is a floor rather than an equality,
# so no cross-tree coupling rides on it.
_WIDER_THAN_ANY_POOL = 25


def _id() -> str:
    return f"contract-{uuid4()}"


def make_record(
    text: str,
    embedding: tuple[float, ...],
    *,
    at: datetime = _AT,
    scope: str = GLOBAL_SCOPE,
    tainted: bool = False,
) -> MemoryRecord:
    return MemoryRecord(
        id=_id(), text=text, embedding=embedding, at=at, scope=scope, tainted=tainted
    )


async def check_empty_search(store: MemoryStore) -> None:
    """A store with no matching rows returns an empty result, not an error."""
    assert list(await store.search((1.0, 0.0, 0.0), k=5)) == []


async def check_ranks_by_similarity(store: MemoryStore) -> None:
    """Search returns the most cosine-similar memory first."""
    near = make_record("near", (1.0, 0.0, 0.0))
    far = make_record("far", (0.0, 1.0, 0.0))
    await store.add(far)
    await store.add(near)
    hits = await store.search((1.0, 0.0, 0.0), k=2)
    assert [hit.record.text for hit in hits] == ["near", "far"]
    assert hits[0].score > hits[1].score


async def check_top_k_truncates(store: MemoryStore) -> None:
    """search(k) returns at most k results."""
    records = [make_record(f"m{i}", (float(i + 1), 0.0, 0.0)) for i in range(3)]
    for record in records:
        await store.add(record)
    assert len(await store.search((1.0, 0.0, 0.0), k=1)) == 1


async def check_roundtrip_fidelity(store: MemoryStore) -> None:
    """A stored memory reads back with its fields intact (float4-exact embedding; instant tz)."""
    original = make_record(
        "unicode ✓ / newline\n",
        (1.0, 0.5, -0.25),
        at=datetime(2026, 7, 3, 17, 45, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        scope="contract-scope",
        tainted=True,
    )
    await store.add(original)
    (hit,) = await store.search((1.0, 0.5, -0.25), k=1, scopes=["contract-scope"])
    assert hit.record.id == original.id
    assert hit.record.text == original.text
    assert tuple(hit.record.embedding) == original.embedding
    assert hit.record.scope == original.scope  # the namespace roundtrips
    assert hit.record.tainted is True  # the untrusted-provenance marker roundtrips (ADR-0019)
    # timestamptz normalizes to UTC, so compare the instant (not the original offset).
    assert hit.record.at == original.at


async def check_scope_filter_isolates_and_unions(store: MemoryStore) -> None:
    """``scopes`` restricts candidates to those namespaces; ``None`` spans every scope."""
    a = make_record("scope-a memory", (1.0, 0.0, 0.0), scope=f"contract-a-{uuid4()}")
    b = make_record("scope-b memory", (1.0, 0.0, 0.0), scope=f"contract-b-{uuid4()}")
    await store.add(a)
    await store.add(b)
    only_a = await store.search((1.0, 0.0, 0.0), k=10, scopes=[a.scope])
    assert a.id in {hit.record.id for hit in only_a}
    assert b.id not in {hit.record.id for hit in only_a}  # filtered out by scope
    both = await store.search((1.0, 0.0, 0.0), k=10, scopes=[a.scope, b.scope])
    assert {a.id, b.id} <= {hit.record.id for hit in both}  # a union of the two scopes


async def check_count_candidates_sizes_the_set_a_search_ranked(store: MemoryStore) -> None:
    """The count is the store's own total, never the length of a result some search returned.

    ``_WIDER_THAN_ANY_POOL`` memories, a search for one. An adapter that answered with ``len(rows)``
    over anything it fetched reads back its own cutoff, which is the one substitution this verb
    exists to rule out, and the size is what makes that catchable: a check holding three memories
    passes any implementation capped at three or more, including one capped at the pool width a
    shipped deployment actually fetches.
    """
    scope = f"contract-count-{uuid4()}"
    for i in range(_WIDER_THAN_ANY_POOL):
        await store.add(make_record(f"counted {i}", (1.0, 0.0, 0.0), scope=scope))
    assert len(await store.search((1.0, 0.0, 0.0), k=1, scopes=[scope])) == 1
    assert await store.count_candidates(scopes=[scope]) == _WIDER_THAN_ANY_POOL


async def check_count_candidates_honours_the_same_scope_filter(store: MemoryStore) -> None:
    """``scopes`` selects the same candidate set it selects for ``search``; ``None`` spans all."""
    a = make_record("scope-a memory", (1.0, 0.0, 0.0), scope=f"contract-ca-{uuid4()}")
    b = make_record("scope-b memory", (0.0, 1.0, 0.0), scope=f"contract-cb-{uuid4()}")
    await store.add(a)
    await store.add(b)
    assert await store.count_candidates(scopes=[a.scope]) == 1  # isolated
    assert await store.count_candidates(scopes=[a.scope, b.scope]) == 2  # unioned
    assert await store.count_candidates() == 2  # unfiltered spans every namespace


async def check_count_candidates_of_nothing_is_zero(store: MemoryStore) -> None:
    """An empty store and an unwritten namespace both count 0, and neither is an error."""
    assert await store.count_candidates() == 0
    assert await store.count_candidates(scopes=[f"contract-unwritten-{uuid4()}"]) == 0


async def check_delete_scope_removes_a_namespace(store: MemoryStore) -> None:
    """``delete_scope`` hard-deletes exactly its namespace, counts it, and spares the rest."""
    scope = f"contract-del-{uuid4()}"
    other = f"contract-keep-{uuid4()}"
    doomed = [make_record(f"doomed {i}", (1.0, 0.0, 0.0), scope=scope) for i in range(2)]
    survivor = make_record("survivor", (1.0, 0.0, 0.0), scope=other)
    for record in (*doomed, survivor):
        await store.add(record)
    removed = await store.delete_scope(scope)
    assert removed == 2  # both memories in the scope, and only those
    assert list(await store.search((1.0, 0.0, 0.0), k=10, scopes=[scope])) == []  # gone
    kept = await store.search((1.0, 0.0, 0.0), k=10, scopes=[other])
    assert [hit.record.id for hit in kept] == [survivor.id]  # the other namespace is untouched


async def check_delete_scope_without_matches_returns_zero(store: MemoryStore) -> None:
    """Deleting a namespace that holds nothing removes nothing and returns 0, not an error."""
    assert await store.delete_scope(f"contract-empty-{uuid4()}") == 0


ALL_CHECKS = (
    check_empty_search,
    check_ranks_by_similarity,
    check_top_k_truncates,
    check_roundtrip_fidelity,
    check_scope_filter_isolates_and_unions,
    check_count_candidates_sizes_the_set_a_search_ranked,
    check_count_candidates_honours_the_same_scope_filter,
    check_count_candidates_of_nothing_is_zero,
    check_delete_scope_removes_a_namespace,
    check_delete_scope_without_matches_returns_zero,
)
