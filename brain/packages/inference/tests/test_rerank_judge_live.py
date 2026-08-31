"""Measure whether the model ranks recall better than the cosine that ships.

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

Three arms since the rank's request was bounded (ADR-0038 bounded-side-calls addendum): the cosine
that ships, the rank as it first shipped (no bounds, so the cortex deliberates before answering),
and the rank as it sends now (no thinking, a cap sized from `k`). Cost and ranking quality are
both reported per arm, because a rank that got cheap by no longer thinking is a different ranker
and the quality does not follow from the cost.

`-s` is required: the print IS the measurement.
"""

import os
import time
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
from cortex_core.drain import drain_text
from cortex_core.rerank_judge import ORDER_ENVELOPE, build_rank_messages, parse_order
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


class _Arm:
    """One ranking's score sheet over the corpus: its placings, its cost, and its fallbacks."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.reciprocal: list[float] = []
        self.first = 0
        self.seconds = 0.0
        self.fell_back = 0

    def record(self, ids: list[str], gold: str) -> None:
        self.reciprocal.append(_reciprocal_rank(ids, gold))
        self.first += int(bool(ids) and ids[0] == gold)

    def line(self, n: int) -> str:
        return (
            f"\n{self.label}: MRR {sum(self.reciprocal) / n:.3f},"
            f" gold first {self.first}/{n}, fell back {self.fell_back}/{n},"
            f" {self.seconds:.1f} s over {n} questions ({self.seconds / n:.1f} s each)"
        )


@pytest.mark.integration
async def test_the_model_rank_is_measured_against_the_cosine_that_ships() -> None:
    """Three arms: the cosine that ships, the rank as it first shipped, and the bounded rank.

    The middle arm is the request `JudgeRecallPolicy` used to send, rebuilt here out of the same
    prompt and envelope with no bounds on it, because the policy itself cannot send that request
    any more. So the corpus scores the ranking twice, once each side of the bounds, which is the
    thing a default move rests on: a rank that got cheap by no longer thinking is a different
    ranker, and whether it is still the better one is not inferable from the cost.
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
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
        cosine, unbounded, bounded = (
            _Arm("cosine (ships)"),
            _Arm("judge, unbounded"),
            _Arm("judge, bounded"),
        )

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
            baseline_ids = [r.hit.record.id for r in baseline.hits]
            cosine.record(baseline_ids, gold)

            started = time.monotonic()
            reply = await drain_text(
                backend,
                _MODEL,
                build_rank_messages(question, scored, k=k, at=_AT),
                schema=ORDER_ENVELOPE,
            )
            unbounded.seconds += time.monotonic() - started
            order = parse_order(reply, pool_size=len(scored), k=k)
            # `None` is a reply nothing can be read out of, which is what falls back. An empty
            # pick is the model declining the pool, and on this corpus (every question has an
            # answer in the notes) that is a wrong answer rather than a failure, so it scores as
            # the empty result it is instead of borrowing the cosine's.
            unbounded.fell_back += int(order is None)
            unbounded_ids = baseline_ids if order is None else [scored[i].record.id for i in order]
            unbounded.record(unbounded_ids, gold)

            started = time.monotonic()
            ranked = await judge.select(scored, query=question, now=_AT, k=k)
            bounded.seconds += time.monotonic() - started
            bounded.fell_back += int(ranked.basis not in (RankBasis.VERDICT, RankBasis.DEMUR))
            ranked_ids = [r.hit.record.id for r in ranked.hits]
            bounded.record(ranked_ids, gold)

            print(  # noqa: T201 -- the measurement IS this test's output
                f"\nQ {question}\n  gold {gold}\n  cosine    {baseline_ids}"
                f"\n  unbounded {unbounded_ids}\n  bounded   {ranked_ids}"
            )

        n = len(_QUESTIONS)
        print(  # noqa: T201 -- the measurement IS this test's output
            f"\nat k={k}, {n} questions over {len(_MEMORIES)} notes:"
            + cosine.line(n)
            + unbounded.line(n)
            + bounded.line(n)
        )
        # The measurement is the point; the assertions pin that the rank ran at all (a reranker
        # that silently fell back would otherwise report the baseline as its own score) and that
        # the bounds are what made it cheap rather than the model having a fast day.
        assert bounded.fell_back < n
        assert bounded.seconds < unbounded.seconds


def _cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    magnitude = (sum(x * x for x in a) ** 0.5) * (sum(x * x for x in b) ** 0.5)
    return dot / magnitude if magnitude else 0.0
