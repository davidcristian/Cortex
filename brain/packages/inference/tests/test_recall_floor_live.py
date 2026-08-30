"""Can a similarity floor give a geometric recall policy the refusal only the judge has?

This is the calibration the relevance-floor deferral asked for, and its answer is no. The floor is
not in the tree: what runs below is the operator a fifth policy would have applied, measured
against the real embedder over the corpus in `recall_corpus.py`, so the number the entry wanted can
be looked for rather than guessed. Integration-marked, excluded from CI and the coverage gate by
the workspace addopts (`-m "not integration"`).

**Needs only the CPU embedder**, not the GPU stack, because a floor reads similarity and never the
model. From the memory override:

    cd brain && CORTEX_MEMORY_EMBEDDER_ENDPOINT=http://127.0.0.1:8081 \
      uv run pytest -m integration --no-cov \
      packages/inference/tests/test_recall_floor_live.py -s

`-s` is required: the print IS the measurement.

Three populations, and the whole question is whether they separate. Answerable questions (their
gold note's cosine, and the best cosine in their pool), `ABSENT` questions (unanswerable but
adjacent, sitting beside notes the corpus holds), and `UNRELATED` ones (unanswerable and about
nothing the corpus has ever mentioned). A floor can only work if some threshold sits above every
unanswerable question's best hit and below every answerable question's gold. The sweep prints what
each candidate threshold silences and what it costs.

The assertions are deliberately about the *instrument* and about the *finding*, not about a shipped
feature. A floor of zero must change nothing and a floor above one must silence everything, which is
what proves the operator is wired at all: a gate that never fires and a gate that works look
identical on a corpus of answerable questions. The finding is asserted too, so it reddens rather
than rots: no threshold separates the populations here, and every threshold that silences all four
`ABSENT` questions also silences answerable ones. **Point this at another `Embedder` and rerun it**
(`CORTEX_MODEL_FILE_EMBED` in the memory override) to reopen the entry: a red finding assertion is
an embedder whose populations do separate, which is the one thing that would make a floor
calibratable.
"""

import math
import os
from collections.abc import Sequence

import httpx
import pytest
from recall_corpus import MEMORIES, QUESTIONS, UNRELATED, Category

from cortex_embedding import LlamaCppEmbedder

_EMBEDDER = os.environ.get("CORTEX_MEMORY_EMBEDDER_ENDPOINT", "http://127.0.0.1:8081")
_EMBED_MODEL = os.environ.get("CORTEX_MEMORY_EMBEDDER_MODEL", "embedding")
_K = 3
_POOL_FACTOR = 4  # config.recall_pool_factor's default, so the pool is the shipped width.
_POOL = _K * _POOL_FACTOR

# The thresholds the sweep prints. A floor is a cosine, so the range is the cosine's; the last one
# is above any cosine there is, which is the absurd end that must silence everything.
_FLOORS = (0.0, 0.30, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80, 0.90, 1.01)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    magnitude = (sum(x * x for x in a) ** 0.5) * (sum(x * x for x in b) ** 0.5)
    return dot / magnitude if magnitude else 0.0


def _floored(pool: Sequence[tuple[str, float]], floor: float) -> list[str]:
    """The operator under test: the raw top-`k` of a pool, minus everything under the floor.

    Pre-filter rather than post-filter, which is the more generous of the two readings: the floor
    decides what counts as a candidate and the policy still fills its `k` from what qualifies, so a
    hit that clears the floor is never displaced by one that does not.
    """
    return [rid for rid, score in pool if score >= floor][:_K]


class _Sweep:
    """One floor's score sheet over the whole corpus."""

    def __init__(self, floor: float, label: str = "") -> None:
        self.floor = floor
        self.label = label
        self.reciprocal = 0.0
        self.answerable = 0
        self.answerable_silent = 0
        self.absent_silent = 0
        self.unrelated_silent = 0
        self.hits = 0
        self.per_category: dict[Category, list[float]] = {c: [] for c in Category}

    def record(self, kept: Sequence[str], gold: str | None, category: Category | None) -> None:
        self.hits += len(kept)
        if category is None:
            self.unrelated_silent += int(not kept)
            return
        if gold is None:
            self.absent_silent += int(not kept)
            return
        self.answerable += 1
        rank = 1.0 / (kept.index(gold) + 1) if gold in kept else 0.0
        self.reciprocal += rank
        self.per_category[category].append(rank)
        self.answerable_silent += int(not kept)

    @property
    def mrr(self) -> float:
        return self.reciprocal / self.answerable if self.answerable else 0.0

    def row(self) -> str:
        cats = "  ".join(
            f"{c.name}:{sum(v) / len(v):.2f}" for c, v in self.per_category.items() if v
        )
        return (
            f"{self.floor:6.4f} | {self.absent_silent}/4 | {self.unrelated_silent}/"
            f"{len(UNRELATED)} | {self.mrr:5.3f} | {self.answerable_silent:2d}/{self.answerable}"
            f" | {self.hits:4d} | {cats}{self.label}"
        )


def _band(values: Sequence[float]) -> str:
    return f"{min(values):.4f} to {max(values):.4f} (n={len(values)}, mean {_mean(values):.4f})"


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


@pytest.mark.integration
async def test_no_similarity_floor_separates_answerable_questions_from_unanswerable_ones() -> None:
    """Sweep a relevance floor over the real embedder: what it silences and what that costs."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        embedder = LlamaCppEmbedder(client, _EMBEDDER, model=_EMBED_MODEL)
        vectors = {rid: tuple(await embedder.embed(text)) for rid, text in MEMORIES.items()}

        pools: dict[str, list[tuple[str, float]]] = {}
        for question in (*QUESTIONS, *UNRELATED):
            asked = await embedder.embed(question)
            ranked = sorted(
                ((rid, _cosine(asked, vec)) for rid, vec in vectors.items()),
                key=lambda pair: pair[1],
                reverse=True,
            )
            pools[question] = ranked[:_POOL]

        gold_scores = [
            score
            for question, (gold, _) in QUESTIONS.items()
            if gold is not None
            for rid, score in pools[question]
            if rid == gold
        ]
        answerable_best = [pools[q][0][1] for q, (gold, _) in QUESTIONS.items() if gold is not None]
        absent_best = [pools[q][0][1] for q, (gold, _) in QUESTIONS.items() if gold is None]
        unrelated_best = [pools[q][0][1] for q in UNRELATED]

        # The grid says what a floor does; this one says what the guarantee costs at its cheapest.
        # It is the lowest floor that silences every adjacent-unanswerable question, derived from
        # the data rather than picked, so the published cost is the minimum price of the promise
        # "a question memory cannot answer returns nothing" rather than an artifact of the grid.
        tight = math.nextafter(max(absent_best), 2.0)
        sweeps = [
            _Sweep(floor, "   <- tightest floor that silences all four" if floor == tight else "")
            for floor in sorted({*_FLOORS, tight})
        ]
        for sweep in sweeps:
            for question, (gold, category) in QUESTIONS.items():
                sweep.record(_floored(pools[question], sweep.floor), gold, category)
            for question in UNRELATED:
                sweep.record(_floored(pools[question], sweep.floor), None, None)

        _report(gold_scores, answerable_best, absent_best, unrelated_best, sweeps)

        # The instrument. A floor of zero must be the unfloored ranking exactly, hit for hit, and a
        # floor above every cosine must leave nothing anywhere; without both, a floor that never
        # fires reads the same as one that works.
        unfloored = next(sweep for sweep in sweeps if sweep.floor == 0.0)
        assert unfloored.hits == _K * (len(QUESTIONS) + len(UNRELATED))
        for question, (gold, _) in QUESTIONS.items():
            assert _floored(pools[question], 0.0) == [rid for rid, _ in pools[question][:_K]]
            assert gold is None or _floored(pools[question], 1.01) == []
        absurd = next(sweep for sweep in sweeps if sweep.floor > 1.0)
        assert absurd.hits == 0
        assert absurd.answerable_silent == absurd.answerable
        assert absurd.absent_silent == 4
        assert absurd.unrelated_silent == len(UNRELATED)

        # The finding, asserted so that an embedder which separates the populations reddens this
        # run rather than passing quietly. Nothing sits between the two bands, and every floor
        # that silences the adjacent-unanswerable population takes answerable questions with it.
        assert min(gold_scores) < max(absent_best), "the populations would separate here"
        silencing = [sweep for sweep in sweeps if sweep.absent_silent == 4]
        assert silencing, "no swept floor silences the unanswerable questions at all"
        assert all(sweep.answerable_silent > 0 for sweep in silencing)
        assert min(sweep.floor for sweep in silencing) == tight


def _report(
    gold_scores: Sequence[float],
    answerable_best: Sequence[float],
    absent_best: Sequence[float],
    unrelated_best: Sequence[float],
    sweeps: Sequence[_Sweep],
) -> None:
    """Print the three populations, then what every candidate floor does to the corpus."""
    lines = [
        f"\n\nat k={_K}, pool {_POOL}, {len(MEMORIES)} notes,"
        f" {len(QUESTIONS)} corpus questions + {len(UNRELATED)} unrelated ones",
        f"\n  answerable, gold note's cosine : {_band(gold_scores)}",
        f"  answerable, best in pool       : {_band(answerable_best)}",
        f"  unanswerable and adjacent      : {_band(absent_best)}",
        f"  unanswerable and unrelated     : {_band(unrelated_best)}",
        f"\n  separation (lowest answerable gold less highest adjacent unanswerable):"
        f" {min(gold_scores) - max(absent_best):+.4f}",
        f"  the same against the unrelated population:"
        f" {min(gold_scores) - max(unrelated_best):+.4f}",
        "\n floor | absent silent | unrelated silent | MRR | answerable silent | hits"
        " | by category",
    ]
    lines.extend(f"  {sweep.row()}" for sweep in sweeps)
    print("\n".join(lines))  # noqa: T201 -- the measurement IS this test's output
