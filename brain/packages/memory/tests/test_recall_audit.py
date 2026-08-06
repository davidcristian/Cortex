"""Behavior of LoggingRecallSink: the recall trail carries the ranking and never the text.

Answering "why did recall return these?" used to mean a throwaway script against the store. The
trail answers it from the logs instead, and the one thing it must never do is take conversation
content along for the ride (ADR-0038 decision 5).
"""

import json
import logging
from datetime import UTC, datetime

import pytest

from cortex_core import MemoryRecord, RankBasis, RankedMemory, Ranking, RecallAudit, ScoredMemory
from cortex_memory import LoggingRecallSink

_AT = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
_PRIVATE = "the family recipe uses smoked paprika"


def _audit(*, basis: RankBasis = RankBasis.EMBER) -> RecallAudit:
    record = MemoryRecord(id="m1", text=_PRIVATE, embedding=(1.0, 0.0), at=_AT, tainted=True)
    ranked = RankedMemory(hit=ScoredMemory(record=record, score=0.87), key=0.71)
    return RecallAudit(
        session_id="s1",
        query="what goes in the recipe?",
        pool_size=20,
        k=5,
        ranking=Ranking(hits=(ranked,), basis=basis),
        at=_AT,
    )


def _logged(caplog: pytest.LogCaptureFixture) -> dict[str, object]:
    (record,) = caplog.records
    payload: dict[str, object] = json.loads(record.getMessage().removeprefix("memory.recall "))
    return payload


async def test_the_trail_carries_the_pool_the_basis_and_each_hits_rank_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="cortex.memory.recall"):
        await LoggingRecallSink().record(_audit())
    payload = _logged(caplog)
    assert payload["pool"] == 20
    assert payload["k"] == 5
    assert payload["basis"] == "ember"
    assert payload["keys_comparable"] is True
    assert payload["hits"] == [{"id": "m1", "key": 0.71, "score": 0.87, "tainted": True}]


async def test_the_trail_says_when_its_keys_may_not_be_compared(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An MMR key was measured against the kept set, and a reader must not threshold it."""
    with caplog.at_level(logging.INFO, logger="cortex.memory.recall"):
        await LoggingRecallSink().record(_audit(basis=RankBasis.SPREAD))
    assert _logged(caplog)["keys_comparable"] is False


async def test_the_trail_carries_no_conversation_text(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="cortex.memory.recall"):
        await LoggingRecallSink().record(_audit())
    (record,) = caplog.records
    assert _PRIVATE not in record.getMessage()  # the recalled memory's text stays out of the logs
    assert "what goes in the recipe?" not in record.getMessage()  # and so does the query
    assert _logged(caplog)["query_chars"] == len("what goes in the recipe?")


async def test_the_fields_also_ride_the_record_for_a_structured_collector(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="cortex.memory.recall"):
        await LoggingRecallSink().record(_audit())
    (record,) = caplog.records
    extras: dict[str, object] = vars(record)
    assert extras["session"] == "s1"
    assert extras["basis"] == "ember"
