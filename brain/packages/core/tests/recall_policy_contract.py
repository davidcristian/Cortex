"""The `RecallPolicy` contract, run over every shipped policy (AGENTS.md: ports before adapters)."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import MemoryRecord, RecallPolicy, ScoredMemory

_NOW = datetime(2026, 9, 17, 6, 0, tzinfo=UTC)
_SIZES_AND_KS = ((6, 1), (6, 3), (2, 5))


@dataclass(frozen=True, slots=True)
class PolicyUnderTest:
    """One policy and the factor its fetch is wider than ``k`` by, which is 1 for raw recall."""

    policy: RecallPolicy
    pool_factor: int


type Check = Callable[[PolicyUnderTest], Awaitable[None]]


def pool(size: int) -> list[ScoredMemory]:
    """``size`` distinct candidates in the store's similarity order, each a day older than the last.

    One-hot embeddings are pairwise orthogonal, so no dedup threshold counts two of them as one.
    """
    return [
        ScoredMemory(
            record=MemoryRecord(
                id=f"m{n}",
                text=f"note {n}",
                embedding=tuple(1.0 if axis == n else 0.0 for axis in range(size)),
                at=_NOW - timedelta(days=n),
            ),
            score=0.9 - 0.1 * n,
        )
        for n in range(size)
    ]


async def _kept(case: PolicyUnderTest, hits: Sequence[ScoredMemory], k: int) -> list[ScoredMemory]:
    ranking = await case.policy.select(hits, query="what did we decide?", now=_NOW, k=k)
    return [ranked.hit for ranked in ranking.hits]


async def the_fetch_is_k_times_the_pool_factor(case: PolicyUnderTest) -> None:
    for k in (1, 5):
        assert case.policy.candidate_k(k) == k * case.pool_factor


async def an_empty_pool_gives_an_empty_ranking(case: PolicyUnderTest) -> None:
    assert await _kept(case, [], 3) == []


async def at_most_k_hits_come_back_each_from_the_pool_once(case: PolicyUnderTest) -> None:
    for size, k in _SIZES_AND_KS:
        hits = pool(size)
        kept = await _kept(case, hits, k)
        assert len(kept) <= k
        assert all(hit in hits for hit in kept)
        assert len({hit.record.id for hit in kept}) == len(kept)


async def the_pool_is_left_as_it_was_handed(case: PolicyUnderTest) -> None:
    hits = pool(6)
    await _kept(case, hits, 3)
    assert hits == pool(6)


async def an_unpruned_selection_keeps_as_many_as_k_allows(case: PolicyUnderTest) -> None:
    for size, k in _SIZES_AND_KS:
        assert len(await _kept(case, pool(size), k)) == min(size, k)


def a_pool_factor_below_one_is_refused(build: Callable[[int], RecallPolicy]) -> None:
    build(1)
    with pytest.raises(ValueError, match="pool_factor must be at least 1"):
        build(0)


ALL_CHECKS: tuple[Check, ...] = (
    the_fetch_is_k_times_the_pool_factor,
    an_empty_pool_gives_an_empty_ranking,
    at_most_k_hits_come_back_each_from_the_pool_once,
    the_pool_is_left_as_it_was_handed,
)
UNPRUNED_CHECKS: tuple[Check, ...] = (an_unpruned_selection_keeps_as_many_as_k_allows,)
