import logging
from datetime import UTC, datetime

import pytest

from cortex_core import (
    DroppedCandidate,
    DroppedCandidates,
    MemoryRecord,
    PlainFormatter,
    RankBasis,
    RankedMemory,
    Ranking,
    RecallAudit,
    ScoredMemory,
    dropped_candidates,
    record_fields,
)
from cortex_memory import LoggingRecallSink

_AT = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
_PRIVATE = "the family recipe uses smoked paprika"
_ALSO_PRIVATE = "the christmas ham is glazed with cider"


def _audit(
    *,
    basis: RankBasis = RankBasis.EMBER,
    ranking: Ranking | None = None,
    pool_size: int = 20,
    available: int = 20,
    dropped: DroppedCandidates | None = None,
) -> RecallAudit:
    record = MemoryRecord(id="m1", text=_PRIVATE, embedding=(1.0, 0.0), at=_AT, tainted=True)
    ranked = RankedMemory(hit=ScoredMemory(record=record, score=0.87), key=0.71)
    return RecallAudit(
        session_id="s1",
        turn_id="t1",
        query="what goes in the recipe?",
        pool_size=pool_size,
        available=available,
        k=5,
        ranking=ranking if ranking is not None else Ranking(hits=(ranked,), basis=basis),
        dropped=dropped if dropped is not None else DroppedCandidates(carried=(), omitted=0),
        at=_AT,
    )


def _logged(caplog: pytest.LogCaptureFixture) -> dict[str, object]:
    """Return the fields on the line, read off the record as the formatter reads them."""
    (record,) = caplog.records
    return record_fields(record)


def _rendered(caplog: pytest.LogCaptureFixture) -> str:
    """Render the whole line an operator reads, through the formatter a process entry installs."""
    (record,) = caplog.records
    return PlainFormatter().format(record)


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


async def test_a_full_pool_and_an_exhausted_store_are_different_lines(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="cortex.memory.recall"):
        await LoggingRecallSink().record(_audit(pool_size=20, available=20))
    exhausted = _logged(caplog)
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="cortex.memory.recall"):
        await LoggingRecallSink().record(_audit(pool_size=20, available=4213))
    truncated = _logged(caplog)

    assert (exhausted["pool"], exhausted["available"]) == (20, 20)
    assert (truncated["pool"], truncated["available"]) == (20, 4213)


async def test_the_trail_says_when_its_keys_may_not_be_compared(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="cortex.memory.recall"):
        await LoggingRecallSink().record(_audit(basis=RankBasis.SPREAD))
    assert _logged(caplog)["keys_comparable"] is False


async def test_a_declined_rank_and_an_empty_pool_are_different_lines(
    caplog: pytest.LogCaptureFixture,
) -> None:
    empty = Ranking(hits=(), basis=RankBasis.DEMUR)
    with caplog.at_level(logging.INFO, logger="cortex.memory.recall"):
        await LoggingRecallSink().record(_audit(ranking=empty))
    declined = _logged(caplog)
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="cortex.memory.recall"):
        await LoggingRecallSink().record(
            _audit(ranking=Ranking(hits=(), basis=RankBasis.ECHO), pool_size=0)
        )
    nothing_to_rank = _logged(caplog)

    assert (declined["basis"], declined["hits"], declined["pool"]) == ("demur", [], 20)
    assert (nothing_to_rank["basis"], nothing_to_rank["hits"], nothing_to_rank["pool"]) == (
        "echo",
        [],
        0,
    )


async def test_the_trail_carries_no_conversation_text(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="cortex.memory.recall"):
        await LoggingRecallSink().record(_audit())
    line = _rendered(caplog)
    assert _PRIVATE not in line
    assert "what goes in the recipe?" not in line
    assert _logged(caplog)["query_chars"] == len("what goes in the recipe?")


async def test_the_trail_names_the_candidates_the_rank_dropped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dropped = DroppedCandidates(
        carried=(DroppedCandidate(id="m2", score=0.83), DroppedCandidate(id="m3", score=0.11)),
        omitted=0,
    )
    with caplog.at_level(logging.INFO, logger="cortex.memory.recall"):
        await LoggingRecallSink().record(_audit(dropped=dropped))
    payload = _logged(caplog)
    assert payload["dropped"] == [{"id": "m2", "score": 0.83}, {"id": "m3", "score": 0.11}]
    assert payload["dropped_omitted"] == 0


async def test_the_trail_says_how_many_drops_its_bound_left_out(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dropped = DroppedCandidates(carried=(DroppedCandidate(id="m2", score=0.83),), omitted=7)
    with caplog.at_level(logging.INFO, logger="cortex.memory.recall"):
        await LoggingRecallSink().record(_audit(dropped=dropped))
    assert _logged(caplog)["dropped_omitted"] == 7


async def test_a_dropped_candidates_text_stays_out_of_the_line_too(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pool = [
        ScoredMemory(
            record=MemoryRecord(id=rid, text=text, embedding=(1.0, 0.0), at=_AT),
            score=score,
        )
        for rid, text, score in (("m0", _PRIVATE, 0.9), ("m1", _ALSO_PRIVATE, 0.4))
    ]
    ranking = Ranking(hits=(), basis=RankBasis.DEMUR)
    audit = _audit(ranking=ranking, dropped=dropped_candidates(pool, ranking))
    with caplog.at_level(logging.INFO, logger="cortex.memory.recall"):
        await LoggingRecallSink().record(audit)
    assert _ALSO_PRIVATE not in _rendered(caplog)
    assert _logged(caplog)["dropped"] == [{"id": "m0", "score": 0.9}, {"id": "m1", "score": 0.4}]


async def test_the_fields_reach_the_line_an_operator_actually_reads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="cortex.memory.recall"):
        await LoggingRecallSink().record(_audit())
    (record,) = caplog.records
    extras: dict[str, object] = vars(record)
    assert extras["session_id"] == "s1"
    assert extras["turn_id"] == "t1"
    assert extras["basis"] == "ember"
    line = _rendered(caplog)
    assert line.startswith("INFO:cortex.memory.recall:memory.recall ")
    assert "session_id=s1" in line
    assert "turn_id=t1" in line
    assert "basis=ember" in line
