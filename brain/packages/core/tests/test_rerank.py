from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    DROPPED_TRAIL_LIMIT,
    DroppedCandidate,
    MemoryRecord,
    MmrRecallPolicy,
    RankBasis,
    RankedMemory,
    Ranking,
    RawRecallPolicy,
    RecallPolicy,
    RecencyMmrRecallPolicy,
    RerankingRecallPolicy,
    ScoredMemory,
    dropped_candidates,
)

_NOW = datetime(2026, 7, 19, 12, 0, 0, tzinfo=UTC)
_DAY = 86400.0


def _hit(
    rid: str, score: float, embedding: tuple[float, ...], *, age_days: float = 0.0
) -> ScoredMemory:
    """A ScoredMemory with a chosen similarity, embedding, and age relative to ``_NOW``."""
    at = _NOW - timedelta(days=age_days)
    return ScoredMemory(
        record=MemoryRecord(id=rid, text=rid, embedding=embedding, at=at), score=score
    )


def _reranker(
    *,
    half_life_days: float = 30.0,
    recency_weight: float = 0.5,
    dedup_threshold: float = 0.98,
    pool_factor: int = 4,
) -> RerankingRecallPolicy:
    return RerankingRecallPolicy(
        half_life_seconds=half_life_days * _DAY,
        recency_weight=recency_weight,
        dedup_threshold=dedup_threshold,
        pool_factor=pool_factor,
    )


async def _kept(policy: RecallPolicy, hits: Sequence[ScoredMemory], *, k: int) -> Sequence[str]:
    """The memory ids a policy keeps, in order."""
    return [ranked.hit.record.id for ranked in (await _rank(policy, hits, k=k)).hits]


async def _rank(policy: RecallPolicy, hits: Sequence[ScoredMemory], *, k: int) -> Ranking:
    """The whole ranking a policy returns, for the assertions about keys and basis."""
    return await policy.select(hits, query="what did we say?", now=_NOW, k=k)


async def test_raw_policy_keeps_store_order_truncated_to_k() -> None:
    hits = [_hit("a", 0.9, (1.0, 0.0)), _hit("b", 0.5, (0.0, 1.0)), _hit("c", 0.1, (1.0, 1.0))]
    kept = await _kept(RawRecallPolicy(), hits, k=2)
    assert kept == ["a", "b"]


async def test_reranking_prefers_a_recent_hit_over_a_slightly_more_similar_stale_one() -> None:
    fresh = _hit("fresh", 0.90, (1.0, 0.0), age_days=0.0)
    stale = _hit("stale", 0.92, (0.0, 1.0), age_days=400.0)
    ranking = await _rank(_reranker(recency_weight=0.5), [stale, fresh], k=2)
    assert [ranked.hit.record.id for ranked in ranking.hits] == ["fresh", "stale"]
    assert ranking.hits[0].hit.score == 0.90
    assert ranking.basis is RankBasis.EMBER
    assert ranking.hits[0].key > ranking.hits[1].key


async def test_reranking_drops_a_near_duplicate_keeping_the_higher_ranked() -> None:
    keep = _hit("keep", 0.90, (1.0, 0.0))
    dupe = _hit("dupe", 0.85, (1.0, 0.0))
    other = _hit("other", 0.80, (0.0, 1.0))
    kept = await _kept(_reranker(), [keep, dupe, other], k=3)
    assert kept == ["keep", "other"]


async def test_reranking_truncates_to_k_after_dedup() -> None:
    hits = [_hit(f"m{i}", 0.9 - i * 0.1, (float(i + 1), 1.0)) for i in range(4)]
    assert len(await _kept(_reranker(), hits, k=2)) == 2


async def test_reranking_clamps_a_future_dated_record() -> None:
    future = _hit("future", 0.40, (1.0, 0.0), age_days=-10.0)
    now = _hit("now", 0.60, (0.0, 1.0), age_days=0.0)
    kept = await _kept(_reranker(recency_weight=0.5), [future, now], k=2)
    assert kept == ["now", "future"]


async def test_reranking_survives_a_far_future_record_without_overflow() -> None:
    # About 7,600 years ahead, with a sub-day half-life. Flooring the age at 0 keeps the
    # exponent non-positive, so `0.5 ** x` cannot raise OverflowError and end the turn.
    far = _hit("far", 0.30, (1.0, 0.0), age_days=-2_800_000.0)
    now = _hit("now", 0.40, (0.0, 1.0), age_days=0.0)
    kept = await _kept(_reranker(half_life_days=0.5, recency_weight=0.5), [far, now], k=2)
    assert kept == ["now", "far"]


async def test_reranking_never_dedups_a_degenerate_zero_embedding() -> None:
    z1 = _hit("z1", 0.5, (0.0, 0.0))
    z2 = _hit("z2", 0.4, (0.0, 0.0))
    kept = await _kept(_reranker(), [z1, z2], k=5)
    assert set(kept) == {"z1", "z2"}


def test_reranking_rejects_a_non_positive_half_life() -> None:
    with pytest.raises(ValueError, match="half_life_seconds must be positive"):
        _reranker(half_life_days=0.0)


def test_reranking_rejects_a_recency_weight_out_of_range() -> None:
    with pytest.raises(ValueError, match="recency_weight must be within"):
        _reranker(recency_weight=1.5)


def test_reranking_rejects_a_dedup_threshold_out_of_range() -> None:
    with pytest.raises(ValueError, match="dedup_threshold must be within"):
        _reranker(dedup_threshold=0.0)


def _mmr(*, relevance_weight: float = 0.5, pool_factor: int = 4) -> MmrRecallPolicy:
    return MmrRecallPolicy(relevance_weight=relevance_weight, pool_factor=pool_factor)


async def test_mmr_prefers_a_diverse_hit_over_a_more_similar_redundant_one() -> None:
    top = _hit("top", 0.90, (1.0, 0.0))
    redundant = _hit("redundant", 0.88, (1.0, 1.0))
    diverse = _hit("diverse", 0.80, (0.0, 1.0))
    ranking = await _rank(_mmr(relevance_weight=0.5), [top, redundant, diverse], k=2)
    assert [ranked.hit.record.id for ranked in ranking.hits] == ["top", "diverse"]
    assert ranking.hits[0].hit.score == 0.90
    assert ranking.basis is RankBasis.SPREAD


async def test_mmr_with_full_relevance_weight_is_top_k_by_score() -> None:
    hits = [_hit("a", 0.90, (1.0, 0.0)), _hit("b", 0.88, (1.0, 1.0)), _hit("c", 0.80, (0.0, 1.0))]
    kept = await _kept(_mmr(relevance_weight=1.0), hits, k=3)
    assert kept == ["a", "b", "c"]


async def test_mmr_never_counts_a_degenerate_zero_embedding_as_redundant() -> None:
    top = _hit("top", 0.90, (1.0, 0.0))
    redundant = _hit("redundant", 0.70, (1.0, 0.0))
    zero = _hit("zero", 0.60, (0.0, 0.0))
    # "redundant" repeats "top", so its marginal score is 0.5 * 0.70 - 0.5 * 1.0 = -0.15, while
    # the zero embedding scores cosine 0 against everything and keeps 0.5 * 0.60 = 0.30.
    kept = await _kept(_mmr(relevance_weight=0.5), [top, redundant, zero], k=2)
    assert kept == ["top", "zero"]


def test_mmr_rejects_a_relevance_weight_out_of_range() -> None:
    with pytest.raises(ValueError, match="relevance_weight must be within"):
        _mmr(relevance_weight=1.5)


def _recency_mmr(
    *,
    half_life_days: float = 30.0,
    recency_weight: float = 0.5,
    relevance_weight: float = 0.5,
    pool_factor: int = 4,
) -> RecencyMmrRecallPolicy:
    return RecencyMmrRecallPolicy(
        half_life_seconds=half_life_days * _DAY,
        recency_weight=recency_weight,
        relevance_weight=relevance_weight,
        pool_factor=pool_factor,
    )


async def test_recency_mmr_prefers_a_recent_hit_for_the_first_pick() -> None:
    fresh = _hit("fresh", 0.80, (1.0, 0.0), age_days=0.0)
    stale = _hit("stale", 0.85, (0.0, 1.0), age_days=400.0)
    ranking = await _rank(_recency_mmr(recency_weight=0.5), [stale, fresh], k=2)
    assert [ranked.hit.record.id for ranked in ranking.hits] == ["fresh", "stale"]
    assert ranking.hits[0].hit.score == 0.80
    assert ranking.basis is RankBasis.SWEEP


async def test_recency_mmr_prefers_a_diverse_hit_over_a_redundant_one() -> None:
    top = _hit("top", 0.90, (1.0, 0.0))
    redundant = _hit("redundant", 0.88, (1.0, 1.0))
    diverse = _hit("diverse", 0.80, (0.0, 1.0))
    kept = await _kept(_recency_mmr(), [top, redundant, diverse], k=2)
    assert kept == ["top", "diverse"]


async def test_recency_mmr_with_full_relevance_weight_is_recency_blended_top_k() -> None:
    hits = [_hit("a", 0.90, (1.0, 0.0)), _hit("b", 0.88, (1.0, 0.0)), _hit("c", 0.80, (0.0, 1.0))]
    kept = await _kept(_recency_mmr(relevance_weight=1.0), hits, k=3)
    assert kept == ["a", "b", "c"]


def test_recency_mmr_rejects_a_non_positive_half_life() -> None:
    with pytest.raises(ValueError, match="half_life_seconds must be positive"):
        _recency_mmr(half_life_days=0.0)


def test_recency_mmr_rejects_a_recency_weight_out_of_range() -> None:
    with pytest.raises(ValueError, match="recency_weight must be within"):
        _recency_mmr(recency_weight=1.5)


def test_recency_mmr_rejects_a_relevance_weight_out_of_range() -> None:
    with pytest.raises(ValueError, match="relevance_weight must be within"):
        _recency_mmr(relevance_weight=-0.1)


async def test_raw_policy_keys_each_hit_by_the_stores_own_cosine() -> None:
    hits = [_hit("a", 0.9, (1.0, 0.0)), _hit("b", 0.5, (0.0, 1.0))]
    ranking = await _rank(RawRecallPolicy(), hits, k=2)
    assert ranking.basis is RankBasis.ECHO
    assert [ranked.key for ranked in ranking.hits] == [0.9, 0.5]


def test_only_the_order_dependent_bases_refuse_comparison() -> None:
    comparable = {basis for basis in RankBasis if basis.comparable}
    assert comparable == {RankBasis.ECHO, RankBasis.EMBER, RankBasis.VERDICT, RankBasis.DEMUR}
    assert not RankBasis.SPREAD.comparable
    assert not RankBasis.SWEEP.comparable


def test_a_declined_ranking_may_not_carry_hits() -> None:
    kept = RankedMemory(hit=_hit("a", 0.9, (1.0, 0.0)), key=0.9)
    with pytest.raises(ValueError, match="DEMUR ranking declines"):
        Ranking(hits=(kept,), basis=RankBasis.DEMUR)
    assert Ranking(hits=(), basis=RankBasis.DEMUR).memories == ()


async def test_an_mmr_key_falls_as_the_kept_set_grows() -> None:
    top = _hit("top", 0.90, (1.0, 0.0))
    redundant = _hit("redundant", 0.85, (1.0, 0.0))
    ranking = await _rank(_mmr(relevance_weight=0.5), [top, redundant], k=2)
    assert ranking.hits[0].key == pytest.approx(0.45)
    assert ranking.hits[1].key == pytest.approx(0.5 * 0.85 - 0.5 * 1.0)


# The pool a shipped recall offers: DEFAULT_RECALL_K times the default recall pool factor. The
# core cannot import either, both being the orchestrator's.
_SHIPPED_POOL = 5 * 4


async def test_the_dropped_set_is_the_pool_minus_what_the_rank_kept() -> None:
    pool = [_hit("a", 0.9, (1.0, 0.0)), _hit("b", 0.6, (0.0, 1.0)), _hit("c", 0.2, (1.0, 1.0))]
    dropped = dropped_candidates(pool, await _rank(RawRecallPolicy(), pool, k=1))
    assert dropped.carried == (
        DroppedCandidate(id="b", score=0.6),
        DroppedCandidate(id="c", score=0.2),
    )
    assert dropped.omitted == 0


async def test_a_dropped_candidate_carries_the_stores_cosine_and_no_rank_key() -> None:
    pool = [_hit("a", 0.9, (1.0, 0.0)), _hit("b", 0.6, (0.0, 1.0))]
    ranking = await _rank(_mmr(relevance_weight=0.5), pool, k=1)
    assert ranking.hits[0].key == pytest.approx(0.45)
    assert dropped_candidates(pool, ranking).carried == (DroppedCandidate(id="b", score=0.6),)


async def test_a_rank_that_kept_nothing_dropped_the_whole_pool() -> None:
    pool = [_hit("a", 0.9, (1.0, 0.0)), _hit("b", 0.6, (0.0, 1.0))]
    declined = Ranking(hits=(), basis=RankBasis.DEMUR)
    assert [candidate.id for candidate in dropped_candidates(pool, declined).carried] == ["a", "b"]


async def test_the_bound_cuts_the_tail_of_the_pools_own_order_and_counts_what_it_cut() -> None:
    pool = [_hit(f"m{i}", 0.9 - i / 100, (1.0, 0.0)) for i in range(6)]
    dropped = dropped_candidates(pool, await _rank(RawRecallPolicy(), pool, k=1), limit=2)
    assert [candidate.id for candidate in dropped.carried] == ["m1", "m2"]
    assert dropped.omitted == 3


async def test_a_shipped_pool_never_reaches_the_bound() -> None:
    pool = [_hit(f"m{i}", 1.0 - i / 100, (1.0, 0.0)) for i in range(_SHIPPED_POOL)]
    dropped = dropped_candidates(pool, await _rank(RawRecallPolicy(), pool, k=5))
    assert len(dropped.carried) == _SHIPPED_POOL - 5
    assert dropped.omitted == 0
    assert _SHIPPED_POOL <= DROPPED_TRAIL_LIMIT
