import os
from datetime import UTC, datetime

import httpx
import pytest
from recall_corpus import EXCHANGES
from served_build import served_build

from cortex_core import (
    JudgeRecallPolicy,
    MemoryRecord,
    RankBasis,
    ScoredMemory,
    SingleResidentModelManager,
)
from cortex_inference import LlamaCppBackend

_MODEL = os.environ.get("CORTEX_MODEL_CORTEX", "cortex")
_ENDPOINT = os.environ.get("CORTEX_INFERENCE_ENDPOINT", "http://127.0.0.1:8080")
_AT = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
_K = 5
_DRAWS = 20


@pytest.mark.integration
async def test_the_judge_is_counted_over_repeated_draws_on_stored_exchanges() -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        await served_build(client, _ENDPOINT, "cortex")
        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        judge = JudgeRecallPolicy(backend, _MODEL, pool_factor=1)
        fell_back = 0
        for question, notes, gold in EXCHANGES:
            hits = [
                ScoredMemory(
                    record=MemoryRecord(id=str(index), text=text, embedding=(), at=_AT), score=0.0
                )
                for index, text in enumerate(notes)
            ]
            held, first, empty = 0, 0, 0
            for _ in range(_DRAWS):
                ranking = await judge.select(hits, query=question, now=_AT, k=_K)
                if ranking.basis not in (RankBasis.VERDICT, RankBasis.DEMUR):
                    fell_back += 1
                    continue
                ids = [ranked.hit.record.id for ranked in ranking.hits]
                held += str(gold) in ids
                first += bool(ids) and ids[0] == str(gold)
                empty += not ids
            print(  # noqa: T201 -- the measurement IS this test's output
                f"\n{question}\n  of {_DRAWS} draws: the asked note held {held}, first {first},"
                f" empty order {empty}"
            )
        assert fell_back == 0
