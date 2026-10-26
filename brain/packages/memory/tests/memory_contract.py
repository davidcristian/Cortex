"""Shared MemoryStore behavior checks. Every implementation must satisfy all of them."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

from cortex_core import (
    GLOBAL_SCOPE,
    MemoryDataError,
    MemoryRecord,
    MemoryStore,
    MemoryStoreError,
)

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)

# More memories than the widest pool a deployment fetches (a recall of 5 times a pool factor of
# 4), so a count that stopped at any cutoff a search applies is too low here rather than correct
# by luck.
_WIDER_THAN_ANY_POOL = 25


@dataclass(frozen=True, slots=True)
class MemoryStoreUnderTest:
    """One implementation plus the one way a test may take its backend away."""

    store: MemoryStore
    break_backend: Callable[[], Awaitable[None]]


type Check = Callable[[MemoryStoreUnderTest], Awaitable[None]]


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


async def _refuses_typed(verb: Callable[[], Awaitable[object]], name: str) -> None:
    """Assert one verb answers a gone backend with ``MemoryStoreError`` and nothing else."""
    try:
        await verb()
    except MemoryDataError as err:
        msg = f"{name} called a gone backend a data defect, which the end of an outage does not fix"
        raise AssertionError(msg) from err
    except MemoryStoreError:
        return
    except Exception as err:
        msg = f"{name} let a {type(err).__name__} through instead of MemoryStoreError"
        raise AssertionError(msg) from err
    msg = f"{name} answered normally with its backend taken away"
    raise AssertionError(msg)


async def check_empty_search(under_test: MemoryStoreUnderTest) -> None:
    """A store with no matching rows returns an empty result, not an error."""
    assert list(await under_test.store.search((1.0, 0.0, 0.0), k=5)) == []


async def check_ranks_by_similarity(under_test: MemoryStoreUnderTest) -> None:
    """Search returns the most cosine-similar memory first."""
    store = under_test.store
    near = make_record("near", (1.0, 0.0, 0.0))
    far = make_record("far", (0.0, 1.0, 0.0))
    await store.add(far)
    await store.add(near)
    hits = await store.search((1.0, 0.0, 0.0), k=2)
    assert [hit.record.text for hit in hits] == ["near", "far"]
    assert hits[0].score > hits[1].score


async def check_top_k_truncates(under_test: MemoryStoreUnderTest) -> None:
    """search(k) returns at most k results."""
    store = under_test.store
    records = [make_record(f"m{i}", (float(i + 1), 0.0, 0.0)) for i in range(3)]
    for record in records:
        await store.add(record)
    assert len(await store.search((1.0, 0.0, 0.0), k=1)) == 1


async def check_roundtrip_fidelity(under_test: MemoryStoreUnderTest) -> None:
    """A stored memory reads back with its fields intact (float4-exact embedding; instant tz)."""
    store = under_test.store
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
    assert hit.record.scope == original.scope
    assert hit.record.tainted is True
    assert hit.record.at == original.at


async def check_scope_filter_isolates_and_unions(under_test: MemoryStoreUnderTest) -> None:
    """``scopes`` restricts candidates to those namespaces; ``None`` spans every scope."""
    store = under_test.store
    a = make_record("scope-a memory", (1.0, 0.0, 0.0), scope=f"contract-a-{uuid4()}")
    b = make_record("scope-b memory", (1.0, 0.0, 0.0), scope=f"contract-b-{uuid4()}")
    await store.add(a)
    await store.add(b)
    only_a = await store.search((1.0, 0.0, 0.0), k=10, scopes=[a.scope])
    assert a.id in {hit.record.id for hit in only_a}
    assert b.id not in {hit.record.id for hit in only_a}
    both = await store.search((1.0, 0.0, 0.0), k=10, scopes=[a.scope, b.scope])
    assert {a.id, b.id} <= {hit.record.id for hit in both}


async def check_count_candidates_sizes_the_set_a_search_ranked(
    under_test: MemoryStoreUnderTest,
) -> None:
    """The count is the store's own total, never the length of a result some search returned."""
    store = under_test.store
    scope = f"contract-count-{uuid4()}"
    for i in range(_WIDER_THAN_ANY_POOL):
        await store.add(make_record(f"counted {i}", (1.0, 0.0, 0.0), scope=scope))
    assert len(await store.search((1.0, 0.0, 0.0), k=1, scopes=[scope])) == 1
    assert await store.count_candidates(scopes=[scope]) == _WIDER_THAN_ANY_POOL


async def check_count_candidates_honours_the_same_scope_filter(
    under_test: MemoryStoreUnderTest,
) -> None:
    """``scopes`` selects the same candidate set it selects for ``search``; ``None`` spans all."""
    store = under_test.store
    a = make_record("scope-a memory", (1.0, 0.0, 0.0), scope=f"contract-ca-{uuid4()}")
    b = make_record("scope-b memory", (0.0, 1.0, 0.0), scope=f"contract-cb-{uuid4()}")
    await store.add(a)
    await store.add(b)
    assert await store.count_candidates(scopes=[a.scope]) == 1
    assert await store.count_candidates(scopes=[a.scope, b.scope]) == 2
    assert await store.count_candidates() == 2


async def check_count_candidates_of_nothing_is_zero(under_test: MemoryStoreUnderTest) -> None:
    """An empty store and an unwritten namespace both count 0, and neither is an error."""
    store = under_test.store
    assert await store.count_candidates() == 0
    assert await store.count_candidates(scopes=[f"contract-unwritten-{uuid4()}"]) == 0


async def check_delete_scope_removes_a_namespace(under_test: MemoryStoreUnderTest) -> None:
    """``delete_scope`` hard-deletes exactly its namespace, counts it, and spares the rest."""
    store = under_test.store
    scope = f"contract-del-{uuid4()}"
    other = f"contract-keep-{uuid4()}"
    doomed = [make_record(f"doomed {i}", (1.0, 0.0, 0.0), scope=scope) for i in range(2)]
    survivor = make_record("survivor", (1.0, 0.0, 0.0), scope=other)
    for record in (*doomed, survivor):
        await store.add(record)
    removed = await store.delete_scope(scope)
    assert removed == 2
    assert list(await store.search((1.0, 0.0, 0.0), k=10, scopes=[scope])) == []
    kept = await store.search((1.0, 0.0, 0.0), k=10, scopes=[other])
    assert [hit.record.id for hit in kept] == [survivor.id]


async def check_delete_scope_without_matches_returns_zero(under_test: MemoryStoreUnderTest) -> None:
    """Deleting a namespace that holds nothing removes nothing and returns 0, not an error."""
    assert await under_test.store.delete_scope(f"contract-empty-{uuid4()}") == 0


async def check_delete_tainted_removes_only_tainted_rows_in_scope(
    under_test: MemoryStoreUnderTest,
) -> None:
    """``delete_tainted`` removes and counts the tainted rows of its scopes, and spares the rest."""
    store = under_test.store
    scope = f"contract-taint-{uuid4()}"
    other = f"contract-taint-keep-{uuid4()}"
    doomed = [
        make_record(f"derived {i}", (1.0, 0.0, 0.0), scope=scope, tainted=True) for i in (1, 2)
    ]
    trusted = make_record("trusted", (1.0, 0.0, 0.0), scope=scope)
    elsewhere = make_record("derived elsewhere", (1.0, 0.0, 0.0), scope=other, tainted=True)
    for record in (*doomed, trusted, elsewhere):
        await store.add(record)
    assert await store.delete_tainted(scopes=[scope]) == 2
    kept = await store.search((1.0, 0.0, 0.0), k=10, scopes=[scope, other])
    assert sorted(hit.record.id for hit in kept) == sorted([trusted.id, elsewhere.id])
    assert await store.delete_tainted(scopes=[scope]) == 0


async def check_count_tainted_counts_only_tainted_rows_in_its_scopes(
    under_test: MemoryStoreUnderTest,
) -> None:
    """``count_tainted`` counts the tainted rows of its scopes and of no other scope."""
    store = under_test.store
    scope = f"contract-taint-count-{uuid4()}"
    other = f"contract-taint-count-other-{uuid4()}"
    assert await store.count_tainted(scopes=[scope]) == 0
    for record in (
        make_record("derived 1", (1.0, 0.0, 0.0), scope=scope, tainted=True),
        make_record("derived 2", (1.0, 0.0, 0.0), scope=scope, tainted=True),
        make_record("trusted", (1.0, 0.0, 0.0), scope=scope),
        make_record("derived elsewhere", (1.0, 0.0, 0.0), scope=other, tainted=True),
    ):
        await store.add(record)
    assert await store.count_tainted(scopes=[scope]) == 2
    assert await store.count_tainted(scopes=[scope, other]) == 3
    assert await store.count_tainted() >= 3
    await store.delete_tainted(scopes=[scope])
    assert await store.count_tainted(scopes=[scope]) == 0


async def check_delete_tainted_without_scopes_reaches_every_namespace(
    under_test: MemoryStoreUnderTest,
) -> None:
    """With no scopes, ``delete_tainted`` removes tainted rows in every namespace."""
    store = under_test.store
    scopes = [f"contract-taint-all-{uuid4()}" for _ in range(2)]
    for scope in scopes:
        await store.add(make_record("derived", (0.0, 1.0, 0.0), scope=scope, tainted=True))
    trusted = make_record("trusted", (0.0, 1.0, 0.0), scope=scopes[0])
    await store.add(trusted)
    assert await store.delete_tainted() >= 2
    kept = await store.search((0.0, 1.0, 0.0), k=10, scopes=scopes)
    assert [hit.record.id for hit in kept] == [trusted.id]


async def check_add_stores_a_record_whose_recalled_memories_all_exist(
    under_test: MemoryStoreUnderTest,
) -> None:
    """A record whose recalled ids are all stored, or that recalled nothing, is stored."""
    store = under_test.store
    scope = f"contract-recalled-{uuid4()}"
    recalled = [
        make_record(f"derived {i}", (1.0, 0.0, 0.0), scope=scope, tainted=True) for i in (1, 2)
    ]
    for record in recalled:
        assert await store.add(record) is True
    ids = [record.id for record in recalled]
    answer = make_record("answer", (1.0, 0.0, 0.0), scope=scope, tainted=True)
    assert await store.add(answer, recalled=[*ids, ids[0]]) is True
    hits = await store.search((1.0, 0.0, 0.0), k=10, scopes=[scope])
    assert answer.id in {hit.record.id for hit in hits}


async def check_add_refuses_a_record_whose_recalled_memory_was_deleted(
    under_test: MemoryStoreUnderTest,
) -> None:
    """A record that recalled a memory a tainted delete removed is not stored, nor counted."""
    store = under_test.store
    scope = f"contract-forgotten-{uuid4()}"
    kept = make_record("kept", (1.0, 0.0, 0.0), scope=scope)
    forgotten = make_record("code 4417", (1.0, 0.0, 0.0), scope=scope, tainted=True)
    for record in (kept, forgotten):
        await store.add(record)
    assert await store.delete_tainted(scopes=[scope]) == 1
    answer = make_record("the code is 4417", (1.0, 0.0, 0.0), scope=scope, tainted=True)
    assert await store.add(answer, recalled=[kept.id, forgotten.id]) is False
    assert await store.count_candidates(scopes=[scope]) == 1
    assert await store.delete_tainted(scopes=[scope]) == 0


async def check_a_lost_backend_crosses_the_port_as_memory_store_error(
    under_test: MemoryStoreUnderTest,
) -> None:
    """Every verb that touches the backend answers a lost one with ``MemoryStoreError``."""
    store = under_test.store
    scope = f"contract-broken-{uuid4()}"
    await store.add(make_record("written before the outage", (1.0, 0.0, 0.0), scope=scope))
    await under_test.break_backend()
    await _refuses_typed(
        lambda: store.add(make_record("after", (1.0, 0.0, 0.0), scope=scope)), "add"
    )
    await _refuses_typed(lambda: store.search((1.0, 0.0, 0.0), k=5, scopes=[scope]), "search")
    await _refuses_typed(lambda: store.count_candidates(scopes=[scope]), "count_candidates")
    await _refuses_typed(lambda: store.count_tainted(scopes=[scope]), "count_tainted")
    await _refuses_typed(lambda: store.delete_scope(scope), "delete_scope")
    await _refuses_typed(lambda: store.delete_tainted(scopes=[scope]), "delete_tainted")


ALL_CHECKS: Sequence[Check] = (
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
    check_a_lost_backend_crosses_the_port_as_memory_store_error,
    check_delete_tainted_removes_only_tainted_rows_in_scope,
    check_delete_tainted_without_scopes_reaches_every_namespace,
    check_count_tainted_counts_only_tainted_rows_in_its_scopes,
    check_add_stores_a_record_whose_recalled_memories_all_exist,
    check_add_refuses_a_record_whose_recalled_memory_was_deleted,
)
