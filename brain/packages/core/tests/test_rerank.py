"""Behavior of the RecallPolicy seam: raw top-k, recency reranking, dedup, and MMR diversity."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    RAW_RECALL_POLICY,
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
)

_NOW = datetime(2026, 7, 19, 12, 0, 0, tzinfo=UTC)
_DAY = 86400.0


def _hit(
    rid: str, score: float, embedding: tuple[float, ...], *, age_days: float = 0.0
) -> ScoredMemory:
    """A ScoredMemory with a controlled similarity, embedding, and age relative to ``_NOW``."""
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
    """The memory ids a policy keeps, in order: the shape these tests pinned before ``select``
    widened to a ``Ranking`` (ADR-0038), so order and membership stay asserted exactly as they were.
    """
    return [ranked.hit.record.id for ranked in (await _rank(policy, hits, k=k)).hits]


async def _rank(policy: RecallPolicy, hits: Sequence[ScoredMemory], *, k: int) -> Ranking:
    """The whole ranking a policy returns, for the assertions about keys and basis."""
    return await policy.select(hits, query="what did we say?", now=_NOW, k=k)


def test_raw_policy_fetches_exactly_k() -> None:
    assert RAW_RECALL_POLICY.candidate_k(5) == 5


async def test_raw_policy_keeps_store_order_truncated_to_k() -> None:
    hits = [_hit("a", 0.9, (1.0, 0.0)), _hit("b", 0.5, (0.0, 1.0)), _hit("c", 0.1, (1.0, 1.0))]
    kept = await _kept(RawRecallPolicy(), hits, k=2)
    assert kept == ["a", "b"]  # order unchanged, truncated


def test_reranking_over_fetches_a_wider_pool() -> None:
    assert _reranker(pool_factor=4).candidate_k(5) == 20


async def test_reranking_prefers_a_recent_hit_over_a_slightly_more_similar_stale_one() -> None:
    fresh = _hit("fresh", 0.90, (1.0, 0.0), age_days=0.0)
    stale = _hit("stale", 0.92, (0.0, 1.0), age_days=400.0)
    ranking = await _rank(_reranker(recency_weight=0.5), [stale, fresh], k=2)
    assert [ranked.hit.record.id for ranked in ranking.hits] == ["fresh", "stale"]
    assert ranking.hits[0].hit.score == 0.90  # the reported score stays the raw cosine
    assert ranking.basis is RankBasis.EMBER  # and the blend is the rank key, named
    assert ranking.hits[0].key > ranking.hits[1].key


async def test_reranking_drops_a_near_duplicate_keeping_the_higher_ranked() -> None:
    keep = _hit("keep", 0.90, (1.0, 0.0))
    dupe = _hit("dupe", 0.85, (1.0, 0.0))  # identical embedding -> cosine 1.0 >= threshold
    other = _hit("other", 0.80, (0.0, 1.0))  # orthogonal -> not a duplicate
    kept = await _kept(_reranker(), [keep, dupe, other], k=3)
    assert kept == ["keep", "other"]  # dupe pruned, other survives


async def test_reranking_truncates_to_k_after_dedup() -> None:
    hits = [_hit(f"m{i}", 0.9 - i * 0.1, (float(i + 1), 1.0)) for i in range(4)]
    assert len(await _kept(_reranker(), hits, k=2)) == 2


async def test_reranking_clamps_a_future_dated_record() -> None:
    # A future ``at`` (clock skew) would make an unclamped decay exceed 1 and lift a less-similar
    # hit above a fresh one; the clamp caps recency at 1.0, so similarity decides the tie.
    future = _hit("future", 0.40, (1.0, 0.0), age_days=-10.0)
    now = _hit("now", 0.60, (0.0, 1.0), age_days=0.0)
    kept = await _kept(_reranker(recency_weight=0.5), [future, now], k=2)
    assert kept == ["now", "future"]


async def test_reranking_survives_a_far_future_record_without_overflow() -> None:
    # A record dated far enough ahead (large clock skew or a corrupt/hand-inserted row) drives the
    # age hugely negative; flooring it at 0 keeps the exponent non-positive, so `0.5 ** x` never
    # overflows to OverflowError (which would crash the whole turn). An aggressive sub-day half-life
    # makes the pre-floor exponent astronomically large, the worst case for the old `min`-after
    # form. The record is treated as maximally recent, so similarity breaks the tie.
    far = _hit(
        "far", 0.30, (1.0, 0.0), age_days=-2_800_000.0
    )  # ~7,600 years ahead (< datetime.max)
    now = _hit("now", 0.40, (0.0, 1.0), age_days=0.0)
    kept = await _kept(_reranker(half_life_days=0.5, recency_weight=0.5), [far, now], k=2)
    assert kept == ["now", "far"]  # no overflow; higher similarity wins


async def test_reranking_never_dedups_a_degenerate_zero_embedding() -> None:
    # A zero-magnitude embedding scores cosine 0.0 against everything, so two of them are never
    # treated as duplicates (exercises the no-magnitude guard).
    z1 = _hit("z1", 0.5, (0.0, 0.0))
    z2 = _hit("z2", 0.4, (0.0, 0.0))
    kept = await _kept(_reranker(), [z1, z2], k=5)
    assert set(kept) == {"z1", "z2"}


async def test_reranking_of_an_empty_pool_is_empty() -> None:
    assert await _kept(_reranker(), [], k=5) == []


def test_reranking_rejects_a_non_positive_half_life() -> None:
    with pytest.raises(ValueError, match="half_life_seconds must be positive"):
        _reranker(half_life_days=0.0)


def test_reranking_rejects_a_recency_weight_out_of_range() -> None:
    with pytest.raises(ValueError, match="recency_weight must be within"):
        _reranker(recency_weight=1.5)


def test_reranking_rejects_a_dedup_threshold_out_of_range() -> None:
    with pytest.raises(ValueError, match="dedup_threshold must be within"):
        _reranker(dedup_threshold=0.0)


def test_reranking_rejects_a_pool_factor_below_one() -> None:
    with pytest.raises(ValueError, match="pool_factor must be at least 1"):
        _reranker(pool_factor=0)


def _mmr(*, relevance_weight: float = 0.5, pool_factor: int = 4) -> MmrRecallPolicy:
    return MmrRecallPolicy(relevance_weight=relevance_weight, pool_factor=pool_factor)


def test_mmr_over_fetches_a_wider_pool() -> None:
    assert _mmr(pool_factor=4).candidate_k(5) == 20


async def test_mmr_prefers_a_diverse_hit_over_a_more_similar_redundant_one() -> None:
    # `b` is more similar to the query than `c` (0.88 > 0.80) and is NOT a near-duplicate of the
    # top hit (cosine 0.707 sits below any sane dedup cutoff, so threshold dedup keeps it), yet MMR
    # still prefers the orthogonal `c` for its second pick: diversity beyond dedup.
    top = _hit("top", 0.90, (1.0, 0.0))
    redundant = _hit("redundant", 0.88, (1.0, 1.0))  # cosine 0.707 to top: similar, not a dupe
    diverse = _hit("diverse", 0.80, (0.0, 1.0))  # orthogonal to top
    ranking = await _rank(_mmr(relevance_weight=0.5), [top, redundant, diverse], k=2)
    assert [ranked.hit.record.id for ranked in ranking.hits] == ["top", "diverse"]
    assert ranking.hits[0].hit.score == 0.90  # the reported score stays the raw cosine
    assert ranking.basis is RankBasis.SPREAD


async def test_mmr_with_full_relevance_weight_is_top_k_by_score() -> None:
    # relevance_weight 1.0 zeroes the diversity penalty, so MMR degenerates to raw top-k order.
    hits = [_hit("a", 0.90, (1.0, 0.0)), _hit("b", 0.88, (1.0, 1.0)), _hit("c", 0.80, (0.0, 1.0))]
    kept = await _kept(_mmr(relevance_weight=1.0), hits, k=3)
    assert kept == ["a", "b", "c"]


async def test_mmr_returns_all_when_the_pool_is_smaller_than_k() -> None:
    hits = [_hit("a", 0.90, (1.0, 0.0)), _hit("b", 0.80, (0.0, 1.0))]
    kept = await _kept(_mmr(), hits, k=5)
    assert kept == ["a", "b"]  # pool exhausted before k, both kept


async def test_mmr_of_an_empty_pool_is_empty() -> None:
    assert await _kept(_mmr(), [], k=5) == []


async def test_mmr_never_counts_a_degenerate_zero_embedding_as_redundant() -> None:
    # A zero-magnitude embedding scores cosine 0.0 against everything (the no-magnitude guard), so
    # it is never penalized as redundant. `zero` takes the last slot over the more-similar
    # `redundant` because `redundant` overlaps the already-kept `top` (cosine 1.0, marginal
    # 0.5*0.70 - 0.5*1.0 = -0.15) while `zero` is unpenalized (0.5*0.60 - 0.5*0.0 = 0.30). A guard
    # counting the zero embedding redundant would flip its marginal negative and pick `redundant`.
    top = _hit("top", 0.90, (1.0, 0.0))
    redundant = _hit("redundant", 0.70, (1.0, 0.0))  # cosine 1.0 to top: penalized
    zero = _hit("zero", 0.60, (0.0, 0.0))  # zero magnitude: cosine 0.0 to all, so never penalized
    kept = await _kept(_mmr(relevance_weight=0.5), [top, redundant, zero], k=2)
    assert kept == ["top", "zero"]  # zero beats the redundant hit


def test_mmr_rejects_a_relevance_weight_out_of_range() -> None:
    with pytest.raises(ValueError, match="relevance_weight must be within"):
        _mmr(relevance_weight=1.5)


def test_mmr_rejects_a_pool_factor_below_one() -> None:
    with pytest.raises(ValueError, match="pool_factor must be at least 1"):
        _mmr(pool_factor=0)


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


def test_recency_mmr_over_fetches_a_wider_pool() -> None:
    assert _recency_mmr(pool_factor=4).candidate_k(5) == 20


async def test_recency_mmr_prefers_a_recent_hit_for_the_first_pick() -> None:
    # The first pick has an empty kept set (redundancy 0 for all), so it is pure recency-blended
    # relevance: the fresher hit wins even though the stale one is slightly more similar.
    fresh = _hit("fresh", 0.80, (1.0, 0.0), age_days=0.0)
    stale = _hit("stale", 0.85, (0.0, 1.0), age_days=400.0)
    ranking = await _rank(_recency_mmr(recency_weight=0.5), [stale, fresh], k=2)
    assert [ranked.hit.record.id for ranked in ranking.hits] == ["fresh", "stale"]
    assert ranking.hits[0].hit.score == 0.80  # the reported score stays the raw cosine
    assert ranking.basis is RankBasis.SWEEP


async def test_recency_mmr_prefers_a_diverse_hit_over_a_redundant_one() -> None:
    # Equal ages neutralize recency, so the diversity axis decides the second pick: MMR still
    # prefers the orthogonal `diverse` over the more-similar `redundant`, as `MmrRecallPolicy` does.
    top = _hit("top", 0.90, (1.0, 0.0))
    redundant = _hit("redundant", 0.88, (1.0, 1.0))  # cosine 0.707 to top: similar, not a dupe
    diverse = _hit("diverse", 0.80, (0.0, 1.0))  # orthogonal to top
    kept = await _kept(_recency_mmr(), [top, redundant, diverse], k=2)
    assert kept == ["top", "diverse"]


async def test_recency_mmr_with_full_relevance_weight_is_recency_blended_top_k() -> None:
    # relevance_weight 1.0 zeroes the diversity penalty, so a redundant hit is kept on relevance
    # alone; with equal ages the recency blend is monotonic in score, so this is top-k by score.
    hits = [_hit("a", 0.90, (1.0, 0.0)), _hit("b", 0.88, (1.0, 0.0)), _hit("c", 0.80, (0.0, 1.0))]
    kept = await _kept(_recency_mmr(relevance_weight=1.0), hits, k=3)
    assert kept == ["a", "b", "c"]  # `b` kept despite duplicating `a`


async def test_recency_mmr_returns_all_when_the_pool_is_smaller_than_k() -> None:
    hits = [_hit("a", 0.90, (1.0, 0.0)), _hit("b", 0.80, (0.0, 1.0))]
    kept = await _kept(_recency_mmr(), hits, k=5)
    assert kept == ["a", "b"]  # pool exhausted before k, both kept


async def test_recency_mmr_of_an_empty_pool_is_empty() -> None:
    assert await _kept(_recency_mmr(), [], k=5) == []


def test_recency_mmr_rejects_a_non_positive_half_life() -> None:
    with pytest.raises(ValueError, match="half_life_seconds must be positive"):
        _recency_mmr(half_life_days=0.0)


def test_recency_mmr_rejects_a_recency_weight_out_of_range() -> None:
    with pytest.raises(ValueError, match="recency_weight must be within"):
        _recency_mmr(recency_weight=1.5)


def test_recency_mmr_rejects_a_relevance_weight_out_of_range() -> None:
    with pytest.raises(ValueError, match="relevance_weight must be within"):
        _recency_mmr(relevance_weight=-0.1)


def test_recency_mmr_rejects_a_pool_factor_below_one() -> None:
    with pytest.raises(ValueError, match="pool_factor must be at least 1"):
        _recency_mmr(pool_factor=0)


async def test_raw_policy_keys_each_hit_by_the_stores_own_cosine() -> None:
    hits = [_hit("a", 0.9, (1.0, 0.0)), _hit("b", 0.5, (0.0, 1.0))]
    ranking = await _rank(RawRecallPolicy(), hits, k=2)
    assert ranking.basis is RankBasis.ECHO
    assert [ranked.key for ranked in ranking.hits] == [0.9, 0.5]


def test_only_the_order_dependent_bases_refuse_comparison() -> None:
    """The family's structure IS the finding: an MMR key was measured against the kept set."""
    comparable = {basis for basis in RankBasis if basis.comparable}
    assert comparable == {RankBasis.ECHO, RankBasis.EMBER, RankBasis.VERDICT, RankBasis.DEMUR}
    assert not RankBasis.SPREAD.comparable
    assert not RankBasis.SWEEP.comparable


def test_a_declined_ranking_may_not_carry_hits() -> None:
    """DEMUR says a policy kept nothing, so a DEMUR ranking holding a hit is a contradiction."""
    kept = RankedMemory(hit=_hit("a", 0.9, (1.0, 0.0)), key=0.9)
    with pytest.raises(ValueError, match="DEMUR ranking declines"):
        Ranking(hits=(kept,), basis=RankBasis.DEMUR)
    assert Ranking(hits=(), basis=RankBasis.DEMUR).memories == ()  # the empty one is the answer


async def test_an_mmr_key_falls_as_the_kept_set_grows() -> None:
    """Why SPREAD is incomparable: the second pick is scored against a non-empty kept set."""
    top = _hit("top", 0.90, (1.0, 0.0))
    redundant = _hit("redundant", 0.85, (1.0, 0.0))
    ranking = await _rank(_mmr(relevance_weight=0.5), [top, redundant], k=2)
    assert ranking.hits[0].key == pytest.approx(0.45)  # 0.5 * 0.90, nothing kept yet
    assert ranking.hits[1].key == pytest.approx(0.5 * 0.85 - 0.5 * 1.0)  # penalised by `top`
