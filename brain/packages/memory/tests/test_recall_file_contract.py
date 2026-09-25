import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cortex_core import (
    DroppedCandidate,
    DroppedCandidates,
    MemoryRecord,
    RankBasis,
    RankedMemory,
    Ranking,
    RecallAudit,
    RecallAuditSink,
    RecordingRecallSink,
    ScoredMemory,
)
from cortex_memory import JsonLinesRecallSink, TeeRecallSink

_AT = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
_HOSTILE = ('s"}\n{"turn_id":"forged"}', "s\r\x00\x1b[31m", "s\u2028\udc80")


@dataclass(frozen=True, slots=True)
class Kept:
    session_id: str
    turn_id: str
    k: int
    basis: str
    hits: tuple[str, ...]
    dropped: tuple[str, ...]
    dropped_omitted: int
    at: str


@dataclass(frozen=True, slots=True)
class SinkUnderTest:
    sink: RecallAuditSink
    kept: Callable[[], list[Kept]]


type Build = Callable[[Path], SinkUnderTest]
type Check = Callable[[SinkUnderTest], Awaitable[None]]


def _audit(turn_id: str = "t1", *, session_id: str = "s1", demur: bool = False) -> RecallAudit:
    record = MemoryRecord(id="m1", text="private", embedding=(1.0, 0.0), at=_AT, tainted=True)
    hits = () if demur else (RankedMemory(hit=ScoredMemory(record=record, score=0.87), key=0.7),)
    return RecallAudit(
        session_id=session_id,
        turn_id=turn_id,
        query="what goes in the recipe?",
        pool_size=3,
        available=40,
        k=5,
        ranking=Ranking(hits=hits, basis=RankBasis.DEMUR if demur else RankBasis.EMBER),
        dropped=DroppedCandidates(
            listed=(DroppedCandidate(id="m2", score=0.5), DroppedCandidate(id="m3", score=0.4)),
            omitted=7,
        ),
        at=_AT,
    )


def _from_audit(audit: RecallAudit) -> Kept:
    return Kept(
        session_id=audit.session_id,
        turn_id=audit.turn_id,
        k=audit.k,
        basis=audit.ranking.basis.value,
        hits=tuple(ranked.hit.record.id for ranked in audit.ranking.hits),
        dropped=tuple(candidate.id for candidate in audit.dropped.listed),
        dropped_omitted=audit.dropped.omitted,
        at=audit.at.isoformat(),
    )


def _read_file(path: Path) -> list[Kept]:
    if not path.exists():
        return []
    rows: list[Kept] = []
    for line in path.read_bytes().decode("ascii").splitlines():
        row = json.loads(line)
        rows.append(
            Kept(
                session_id=row["session_id"],
                turn_id=row["turn_id"],
                k=row["k"],
                basis=row["basis"],
                hits=tuple(hit["id"] for hit in row["hits"]),
                dropped=tuple(candidate["id"] for candidate in row["dropped"]),
                dropped_omitted=row["dropped_omitted"],
                at=row["at"],
            )
        )
    return rows


def _fake(_directory: Path) -> SinkUnderTest:
    sink = RecordingRecallSink()
    return SinkUnderTest(sink, lambda: [_from_audit(audit) for audit in sink.audits])


def _file(directory: Path) -> SinkUnderTest:
    path = directory / "recall.jsonl"
    return SinkUnderTest(JsonLinesRecallSink(path), lambda: _read_file(path))


def _tee(directory: Path) -> SinkUnderTest:
    path = directory / "recall.jsonl"
    sink = TeeRecallSink((RecordingRecallSink(), JsonLinesRecallSink(path)))
    return SinkUnderTest(sink, lambda: _read_file(path))


async def keeps_nothing_before_a_recall(under: SinkUnderTest) -> None:
    assert under.kept() == []


async def keeps_each_recall_in_order(under: SinkUnderTest) -> None:
    first, second = _audit("t1"), _audit("t2")
    await under.sink.record(first)
    await under.sink.record(second)
    assert under.kept() == [_from_audit(first), _from_audit(second)]


async def keeps_a_declined_rank_with_no_hits(under: SinkUnderTest) -> None:
    audit = _audit(demur=True)
    await under.sink.record(audit)
    assert under.kept() == [_from_audit(audit)]


async def keeps_a_hostile_session_id_exactly(under: SinkUnderTest) -> None:
    audits = [_audit(f"t{index}", session_id=text) for index, text in enumerate(_HOSTILE)]
    for audit in audits:
        await under.sink.record(audit)
    assert under.kept() == [_from_audit(audit) for audit in audits]


CHECKS: tuple[Check, ...] = (
    keeps_nothing_before_a_recall,
    keeps_each_recall_in_order,
    keeps_a_declined_rank_with_no_hits,
    keeps_a_hostile_session_id_exactly,
)


@pytest.mark.parametrize("build", [_fake, _file, _tee], ids=["fake", "file", "tee"])
@pytest.mark.parametrize("check", CHECKS, ids=[check.__name__ for check in CHECKS])
async def test_sink_meets_the_contract(build: Build, check: Check, tmp_path: Path) -> None:
    await check(build(tmp_path))
