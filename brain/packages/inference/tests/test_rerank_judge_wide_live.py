"""Does the judge still win on a corpus that was not built for it? Scored per category.

Integration-marked: excluded from CI and the coverage gate by the workspace addopts
(`-m "not integration"`). Needs the gpu stack for the cortex and the memory override's CPU
embedder:

    cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 \
      CORTEX_MEMORY_EMBEDDER_ENDPOINT=http://127.0.0.1:8081 \
      uv run pytest -m integration --no-cov \
      packages/inference/tests/test_rerank_judge_wide_live.py -s

`test_rerank_judge_live.py` measures the same policy over the ten notes and six questions the
recommendation was first written on, all of them the one case the judge was bought for. This run
widens the input to `recall_corpus.py`, whose other five categories are cases where the cosine
should win or tie, where a reader can overthink a question the geometry already had right, and
where the correct answer is no hit at all. **The aggregate is reported last and matters least**:
a mean over six categories is exactly the shape that hides one policy being worse on one of them.

Three arms. The cosine that ships, the bounded judge on its real `select` path, and a **reversed
cosine as a control on the scorer itself**: a ranking known to be bad, whose score must collapse.
A scoring harness nobody has watched fail is not evidence, and the reversed arm is what makes the
other two numbers mean something.

The pool is the production shape rather than the whole corpus: `MemoryRecaller` over-fetches
`k * pool_factor` by cosine and the policy ranks that, so a gold note the cosine leaves out of the
pool is one the judge never sees. `gold in pool` is reported per category for exactly that reason.

`-s` is required: the print IS the measurement.
"""

import os
import time
from datetime import UTC, datetime

import httpx
import pytest
from recall_corpus import MEMORIES, QUESTIONS, Category

from cortex_core import (
    JudgeRecallPolicy,
    MemoryRecord,
    RankBasis,
    RawRecallPolicy,
    ScoredMemory,
    SingleResidentModelManager,
)
from cortex_core.drain import drain_text
from cortex_core.rerank_judge import ORDER_ENVELOPE, build_rank_messages, parse_order, rank_bounds
from cortex_embedding import LlamaCppEmbedder
from cortex_inference import LlamaCppBackend

_MODEL = os.environ.get("CORTEX_MODEL_CORTEX", "cortex")
_ENDPOINT = os.environ.get("CORTEX_INFERENCE_ENDPOINT", "http://127.0.0.1:8080")
_EMBEDDER = os.environ.get("CORTEX_MEMORY_EMBEDDER_ENDPOINT", "http://127.0.0.1:8081")
_AT = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
_K = 3
_POOL_FACTOR = 4  # config.recall_pool_factor's default, so the pool is the shipped width.


class _Tally:
    """One arm's score sheet for one category, kept per category because the mean hides."""

    def __init__(self) -> None:
        self.answerable = 0
        self.reciprocal = 0.0
        self.first = 0
        self.in_pool = 0
        self.absent = 0
        self.absent_empty = 0
        self.short = 0
        self.short_right = 0
        self.fell_back = 0
        self.declined = 0
        self.seconds = 0.0
        self.asked = 0

    def record(self, ids: list[str], gold: str | None) -> None:
        """Score one question: reciprocal rank when there is a gold, abstention when not."""
        self.asked += 1
        if gold is None:
            self.absent += 1
            self.absent_empty += int(not ids)
            self.short += int(len(ids) < _K)
            self.short_right += int(not ids)
            return
        self.answerable += 1
        self.reciprocal += 1.0 / (ids.index(gold) + 1) if gold in ids else 0.0
        self.first += int(bool(ids) and ids[0] == gold)
        if len(ids) < _K:
            self.short += 1
            self.short_right += int(gold in ids)

    @property
    def mrr(self) -> float:
        return self.reciprocal / self.answerable if self.answerable else 0.0

    def cell(self) -> str:
        if self.answerable:
            return (
                f"MRR {self.mrr:.3f}  first {self.first}/{self.answerable}"
                f"  short {self.short}/{self.asked} ({self.short_right} right)"
                f"  declined {self.declined}/{self.asked}  fallback {self.fell_back}/{self.asked}"
            )
        return (
            f"returned nothing {self.absent_empty}/{self.absent}"
            f"  short {self.short}/{self.asked}  declined {self.declined}/{self.asked}"
            f"  fallback {self.fell_back}/{self.asked}"
        )


def _cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    magnitude = (sum(x * x for x in a) ** 0.5) * (sum(x * x for x in b) ** 0.5)
    return dot / magnitude if magnitude else 0.0


@pytest.mark.integration
async def test_the_judge_is_scored_per_category_on_a_corpus_not_built_for_it() -> None:
    """Cosine, judge and a reversed control over six categories, scored one category at a time."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        embedder = LlamaCppEmbedder(client, _EMBEDDER, model="embedding")
        vectors = {rid: tuple(await embedder.embed(text)) for rid, text in MEMORIES.items()}
        pool = [
            ScoredMemory(
                record=MemoryRecord(id=rid, text=MEMORIES[rid], embedding=vec, at=_AT), score=0.0
            )
            for rid, vec in vectors.items()
        ]

        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        judge = JudgeRecallPolicy(backend, _MODEL, pool_factor=_POOL_FACTOR)
        raw = RawRecallPolicy()
        arms: dict[str, dict[Category, _Tally]] = {
            label: {category: _Tally() for category in Category}
            for label in ("cosine (ships)", "judge (bounded)", "reversed (control)")
        }
        diagnosed: list[str] = []

        for question, (gold, category) in QUESTIONS.items():
            query = tuple(await embedder.embed(question))
            ranked_pool = sorted(
                (
                    ScoredMemory(record=hit.record, score=_cosine(query, vectors[hit.record.id]))
                    for hit in pool
                ),
                key=lambda hit: hit.score,
                reverse=True,
            )
            candidates = ranked_pool[: judge.candidate_k(_K)]

            baseline = await raw.select(candidates, query=question, now=_AT, k=_K)
            cosine_ids = [r.hit.record.id for r in baseline.hits]
            control_ids = [hit.record.id for hit in reversed(candidates)][:_K]

            started = time.monotonic()
            verdict = await judge.select(candidates, query=question, now=_AT, k=_K)
            elapsed = time.monotonic() - started
            judge_ids = [r.hit.record.id for r in verdict.hits]
            # Three outcomes now, not two: the judge ranked (VERDICT), the judge declined the whole
            # pool (DEMUR, which is an answer and the thing this policy can do that the cosine
            # cannot), or it could not be reached or believed and something else ranked.
            declined = verdict.basis is RankBasis.DEMUR
            fell_back = verdict.basis not in (RankBasis.VERDICT, RankBasis.DEMUR)

            arms["cosine (ships)"][category].record(cosine_ids, gold)
            arms["reversed (control)"][category].record(control_ids, gold)
            judged = arms["judge (bounded)"][category]
            judged.record(judge_ids, gold)
            judged.seconds += elapsed
            judged.fell_back += int(fell_back)
            judged.declined += int(declined)
            if gold is not None and gold in [hit.record.id for hit in candidates]:
                # Recorded on one arm only: the pool is the cosine's, and every arm ranks it.
                arms["cosine (ships)"][category].in_pool += 1

            if fell_back:
                # A fallback used to be either the model declining to pick or a reply the policy
                # could not parse, and only the raw text told them apart. The refusal now has its
                # own basis, so a fallback here is the second kind and the probe says which reply
                # produced it: that reading is the point of re-sampling rather than inferring.
                probe = await drain_text(
                    backend,
                    _MODEL,
                    build_rank_messages(question, candidates, k=_K, at=_AT),
                    schema=ORDER_ENVELOPE,
                    bounds=rank_bounds(_K),
                )
                parsed = parse_order(probe, pool_size=len(candidates), k=_K)
                diagnosed.append(f"    {question!r} -> {probe!r} parses to {parsed}")

            outcome = " (fell back)" if fell_back else " (declined)" if declined else ""
            print(  # noqa: T201 -- the measurement IS this test's output
                f"\n[{category.name}] {question}\n  gold {gold}"
                f"\n  cosine   {cosine_ids}\n  judge    {judge_ids}"
                f"{outcome}\n  control  {control_ids}"
            )

        _report(arms, diagnosed)
        # The measurement is the point. These pin that the run measured anything at all: the
        # control must score far below the cosine (a scorer that cannot fail is not a scorer),
        # and the judge must have ranked at least some questions itself rather than reporting
        # its fallback's work as its own.
        assert _mean(arms["reversed (control)"]) < _mean(arms["cosine (ships)"]) / 2
        assert sum(t.fell_back for t in arms["judge (bounded)"].values()) < len(QUESTIONS)


def _mean(tallies: dict[Category, _Tally]) -> float:
    """Corpus-wide MRR over the answerable questions, pooled rather than averaged per category."""
    total = sum(t.answerable for t in tallies.values())
    return sum(t.reciprocal for t in tallies.values()) / total if total else 0.0


def _report(arms: dict[str, dict[Category, _Tally]], diagnosed: list[str]) -> None:
    """Print the per-category sheet, then the aggregate that the per-category sheet outranks."""
    lines = [
        f"\n\nat k={_K}, pool {_K * _POOL_FACTOR}, {len(QUESTIONS)} questions"
        f" over {len(MEMORIES)} notes"
    ]
    for category in Category:
        counts = arms["cosine (ships)"][category]
        lines.append(
            f"\n{category.value}  (n={counts.asked}, gold in pool {counts.in_pool}"
            f"/{counts.answerable})"
        )
        for label, tallies in arms.items():
            lines.append(f"    {label:<20} {tallies[category].cell()}")
    judge = arms["judge (bounded)"]
    seconds = sum(t.seconds for t in judge.values())
    lines.append(
        f"\naggregate MRR: cosine {_mean(arms['cosine (ships)']):.3f}"
        f"  judge {_mean(judge):.3f}  control {_mean(arms['reversed (control)']):.3f}"
    )
    lines.append(
        f"judge cost {seconds:.1f} s over {len(QUESTIONS)} recalls"
        f" ({seconds / len(QUESTIONS):.2f} s each),"
        f" declined {sum(t.declined for t in judge.values())}/{len(QUESTIONS)},"
        f" fell back {sum(t.fell_back for t in judge.values())}/{len(QUESTIONS)}"
    )
    if diagnosed:
        lines.append("fallback replies, re-sampled to read what the policy could not use:")
        lines.extend(diagnosed)
    print("\n".join(lines))  # noqa: T201 -- the measurement IS this test's output
