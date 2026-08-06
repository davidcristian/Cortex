"""Does the model rank recall better than the cosine that ships? Measured, not assumed.

Integration-marked: excluded from CI and the coverage gate by the workspace addopts
(`-m "not integration"`). Needs the gpu stack for the cortex and the memory override's CPU embedder:

    cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 \
      CORTEX_MEMORY_EMBEDDER_ENDPOINT=http://127.0.0.1:8081 \
      uv run pytest -m integration --no-cov packages/inference/tests/test_rerank_judge_live.py -s

The corpus is built so the two rankings can disagree: every gold memory answers its question in
words the question does not use, and every distractor shares the question's vocabulary while
answering nothing. That is exactly the case a cosine cannot see and the case a reranker is bought
for; a corpus of paraphrases would flatter both. The measurement is reciprocal rank of the gold
memory, averaged over the questions, plus how often the gold memory is placed first.
"""

import os
from datetime import UTC, datetime

import httpx
import pytest

from cortex_core import (
    JudgeRecallPolicy,
    MemoryRecord,
    RankBasis,
    RawRecallPolicy,
    ScoredMemory,
    SingleResidentModelManager,
)
from cortex_embedding import LlamaCppEmbedder
from cortex_inference import LlamaCppBackend

_MODEL = os.environ.get("CORTEX_MODEL_CORTEX", "cortex")
_ENDPOINT = os.environ.get("CORTEX_INFERENCE_ENDPOINT", "http://127.0.0.1:8080")
_EMBEDDER = os.environ.get("CORTEX_MEMORY_EMBEDDER_ENDPOINT", "http://127.0.0.1:8081")
_AT = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)

# id -> remembered text. Ten notes; six of them are the answer to one question each.
_MEMORIES: dict[str, str] = {
    "state": (
        "we settled on Redis for anything a turn is holding, and Postgres for what outlives it"
    ),
    "state-noise": "the Redis container kept restarting until the healthcheck interval was raised",
    "gpu": "only one model sits on the card at a time and the others are evicted before it loads",
    "gpu-noise": "the card arrived on Tuesday and the box was dented",
    "coffee": "she takes hers black, no sugar, and refuses anything from a pod machine",
    "coffee-noise": "the coffee machine in the kitchen was replaced in March",
    "flight": "the return leg is the red-eye that lands just after six in the morning",
    "flight-noise": "flights were cheaper the week before but the dates did not work",
    "deploy": (
        "nothing ships on a Friday, and the person who merges it is the person who watches it"
    ),
    "deploy-noise": "the deploy script lives in the scripts directory next to the linters",
}

# question -> the note that actually answers it.
_QUESTIONS: dict[str, str] = {
    "where are we keeping things while a conversation is in progress?": "state",
    "can two of them be loaded at once?": "gpu",
    "how does she like her coffee?": "coffee",
    "what time do we get back?": "flight",
    "is it alright to release at the end of the week?": "deploy",
    "who is on the hook after a release goes out?": "deploy",
}


def _reciprocal_rank(order: list[str], gold: str) -> float:
    """1 / the gold note's placing, or 0.0 when it is not in the returned list at all."""
    return 1.0 / (order.index(gold) + 1) if gold in order else 0.0


@pytest.mark.integration
async def test_the_model_rank_is_measured_against_the_cosine_that_ships() -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        embedder = LlamaCppEmbedder(client, _EMBEDDER, model="embedding")
        pool: list[ScoredMemory] = []
        vectors: dict[str, tuple[float, ...]] = {}
        for rid, text in _MEMORIES.items():
            vectors[rid] = tuple(await embedder.embed(text))
            pool.append(
                ScoredMemory(
                    record=MemoryRecord(id=rid, text=text, embedding=vectors[rid], at=_AT),
                    score=0.0,
                )
            )

        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        judge = JudgeRecallPolicy(backend, _MODEL, pool_factor=1)
        raw = RawRecallPolicy()
        k = 3
        cosine_rr: list[float] = []
        judge_rr: list[float] = []
        cosine_first = 0
        judge_first = 0
        fell_back = 0

        for question, gold in _QUESTIONS.items():
            query = tuple(await embedder.embed(question))
            scored = sorted(
                (
                    ScoredMemory(record=hit.record, score=_cosine(query, vectors[hit.record.id]))
                    for hit in pool
                ),
                key=lambda hit: hit.score,
                reverse=True,
            )
            baseline = await raw.select(scored, query=question, now=_AT, k=k)
            ranked = await judge.select(scored, query=question, now=_AT, k=k)
            if ranked.basis is not RankBasis.VERDICT:
                fell_back += 1
            baseline_ids = [r.hit.record.id for r in baseline.hits]
            ranked_ids = [r.hit.record.id for r in ranked.hits]
            cosine_rr.append(_reciprocal_rank(baseline_ids, gold))
            judge_rr.append(_reciprocal_rank(ranked_ids, gold))
            cosine_first += int(bool(baseline_ids) and baseline_ids[0] == gold)
            judge_first += int(bool(ranked_ids) and ranked_ids[0] == gold)
            print(  # noqa: T201 -- the measurement IS this test's output
                f"\nQ {question}\n  gold {gold}\n  cosine {baseline_ids}\n  judge  {ranked_ids}"
            )

        n = len(_QUESTIONS)
        print(  # noqa: T201 -- the measurement IS this test's output
            f"\nMRR at {k}: cosine {sum(cosine_rr) / n:.3f}, judge {sum(judge_rr) / n:.3f}"
            f"\nGold placed first: cosine {cosine_first}/{n}, judge {judge_first}/{n}"
            f"\nFell back to cosine: {fell_back}/{n}"
        )
        # The measurement is the point; the assertion only pins that the rank ran at all, because
        # a reranker that silently fell back would otherwise report the baseline as its own score.
        assert fell_back < n


def _cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    magnitude = (sum(x * x for x in a) ** 0.5) * (sum(x * x for x in b) ** 0.5)
    return dot / magnitude if magnitude else 0.0
