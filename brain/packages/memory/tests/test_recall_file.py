import json
import logging
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cortex_core import (
    DroppedCandidates,
    MemoryRecord,
    RankBasis,
    RankedMemory,
    Ranking,
    RecallAudit,
    ScoredMemory,
    record_fields,
)
from cortex_memory import JsonLinesRecallSink, recall_fields

_AT = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
_QUERY = "what goes in the family recipe?"
_TEXT = "the family recipe uses smoked paprika"


def _audit(turn_id: str = "t1", *, score: float = 0.87) -> RecallAudit:
    record = MemoryRecord(id="m1", text=_TEXT, embedding=(1.0, 0.0), at=_AT, tainted=False)
    return RecallAudit(
        session_id="s1",
        turn_id=turn_id,
        query=_QUERY,
        pool_size=20,
        available=20,
        k=5,
        ranking=Ranking(
            hits=(RankedMemory(hit=ScoredMemory(record=record, score=score), key=0.71),),
            basis=RankBasis.EMBER,
        ),
        dropped=DroppedCandidates(listed=(), omitted=0),
        at=_AT,
    )


def _rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines()]


async def test_a_record_holds_the_fields_the_log_line_holds(tmp_path: Path) -> None:
    path = tmp_path / "recall.jsonl"
    await JsonLinesRecallSink(path).record(_audit())
    record = logging.LogRecord("cortex.memory.recall", logging.INFO, "p.py", 1, "m", (), None)
    record.__dict__.update(recall_fields(_audit()))
    (row,) = _rows(path)
    assert row == record_fields(record)
    assert row["query_chars"] == len(_QUERY)
    assert _QUERY not in path.read_text(encoding="ascii")
    assert _TEXT not in path.read_text(encoding="ascii")


async def test_a_non_finite_score_is_kept_as_the_lines_text(tmp_path: Path) -> None:
    path = tmp_path / "recall.jsonl"
    await JsonLinesRecallSink(path).record(_audit(score=float("nan")))
    (row,) = _rows(path)
    assert row["hits"] == '[{"id":"m1","key":0.71,"score":NaN,"tainted":false}]'


async def test_records_are_appended_one_per_line_owner_only(tmp_path: Path) -> None:
    path = tmp_path / "recall.jsonl"
    sink = JsonLinesRecallSink(path)
    await sink.record(_audit("t1"))
    await sink.record(_audit("t2"))
    assert [row["turn_id"] for row in _rows(path)] == ["t1", "t2"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


async def test_a_torn_last_line_is_closed_before_the_next_record(tmp_path: Path) -> None:
    path = tmp_path / "recall.jsonl"
    path.write_bytes(b'{"turn_id":"t')
    await JsonLinesRecallSink(path).record(_audit("t1"))
    torn, line = path.read_bytes().split(b"\n", 1)
    assert torn == b'{"turn_id":"t'
    assert json.loads(line)["turn_id"] == "t1"
    assert line.count(b"\n") == 1


async def test_a_file_moved_away_is_created_again(tmp_path: Path) -> None:
    path = tmp_path / "recall.jsonl"
    sink = JsonLinesRecallSink(path)
    await sink.record(_audit("t1"))
    path.rename(tmp_path / "recall.jsonl.1")
    await sink.record(_audit("t2"))
    assert [row["turn_id"] for row in _rows(path)] == ["t2"]


async def test_a_refused_append_is_a_gap_naming_the_file_and_the_turn(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "missing" / "recall.jsonl"
    await JsonLinesRecallSink(path).record(_audit("t9"))
    (record,) = caplog.records
    assert (record.levelno, record.name, record.getMessage()) == (
        logging.WARNING,
        "cortex_memory.audit_file",
        "memory.recall.gap",
    )
    fields = record_fields(record)
    assert set(fields) == {"error", "path", "turn_id"}
    assert (fields["path"], fields["turn_id"]) == (str(path), "t9")
    assert str(fields["error"]).startswith("FileNotFoundError: [Errno 2]")
