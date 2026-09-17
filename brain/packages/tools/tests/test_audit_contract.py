import json
from collections.abc import Callable
from pathlib import Path

import pytest
from audit_contract import CHECKS, Check, Kept, SinkUnderTest

from cortex_core import RecordingAuditSink
from cortex_tools import JsonLinesAuditSink, TeeAuditSink

type Build = Callable[[Path], SinkUnderTest]


def _fake(_directory: Path) -> SinkUnderTest:
    sink = RecordingAuditSink()

    def kept() -> list[Kept]:
        return [
            Kept(
                tool=record.name,
                ok=record.ok,
                trust=record.trust.value,
                at=record.at.isoformat(),
                call_id=record.call_id,
                session_id=record.session_id,
                turn_id=record.turn_id,
                task_id=record.task_id,
                item_id=record.item_id,
            )
            for record in sink.records
        ]

    return SinkUnderTest(sink, kept)


def _read_file(path: Path) -> list[Kept]:
    """Every line of the file as a row; a line that is not one JSON object fails the check."""
    rows: list[Kept] = []
    for line in path.read_bytes().decode("ascii").splitlines():
        row = json.loads(line)
        rows.append(Kept(**{key: row[key] for key in row if key in Kept.__dataclass_fields__}))
    return rows


def _file(directory: Path) -> SinkUnderTest:
    path = directory / "audit.jsonl"
    return SinkUnderTest(JsonLinesAuditSink(path), lambda: _read_file(path))


def _tee(directory: Path) -> SinkUnderTest:
    path = directory / "audit.jsonl"
    sink = TeeAuditSink((RecordingAuditSink(), JsonLinesAuditSink(path)))
    return SinkUnderTest(sink, lambda: _read_file(path))


@pytest.mark.parametrize("build", [_fake, _file, _tee], ids=["fake", "file", "tee"])
@pytest.mark.parametrize("check", CHECKS, ids=[check.__name__ for check in CHECKS])
async def test_sink_meets_the_contract(build: Build, check: Check, tmp_path: Path) -> None:
    await check(build(tmp_path))
