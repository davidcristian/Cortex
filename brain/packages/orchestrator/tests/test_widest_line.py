import ast
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

import cortex_orchestrator
from cortex_core import (
    CUT,
    VALUE_CHARS,
    DroppedCandidate,
    DroppedCandidates,
    HashEmbedder,
    InMemoryMemoryStore,
    MemoryRecaller,
    PlainFormatter,
    RankBasis,
    RankedMemory,
    Ranking,
    RecallAudit,
    ScoredMemory,
    SystemClock,
    ToolInvocation,
    Trust,
    record_fields,
)
from cortex_memory import JsonLinesRecallSink, LoggingRecallSink
from cortex_tools import JsonLinesAuditSink, LoggingAuditSink

# A container's log driver ends a message at 16 KiB, so 16,383 characters plus the newline is
# the last line that stays one entry.
ONE_DOCKER_MESSAGE = 16383

_MARKER = CUT[: CUT.index("{")]

_WIDE = "w" * (VALUE_CHARS * 2)

_MINTED = "0e2f4a1b-6c3d-4e5f-8a9b-0c1d2e3f4a5b"

_AT = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)

# The widest any Python float renders, at 24 characters.
_WIDEST_FLOAT = -1.7976931348623157e308

# The widest candidate count and the widest hit count a real recall writes. They come from
# different lines, so the record built below is wider than any one recall can produce.
_DROPPED = 20
_HITS = 5


def _line(record: logging.LogRecord) -> str:
    """The line an operator reads, through the formatter a process entry installs."""
    return PlainFormatter().format(record)


async def test_the_widest_tool_audit_line_fits_one_log_driver_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    await LoggingAuditSink().record(
        ToolInvocation(
            name=_WIDE,
            arguments={"instruction": _WIDE},
            ok=False,
            detail=_WIDE,
            at=_AT,
            trust=Trust.UNTRUSTED,
            call_id=_WIDE,
            session_id=_WIDE,
            turn_id=_MINTED,
            task_id=_MINTED,
            item_id=_MINTED,
        )
    )
    (record,) = caplog.records
    line = _line(record)
    assert len(line) < ONE_DOCKER_MESSAGE
    assert line.count(_MARKER) == 5
    assert set(record_fields(record)) == {
        "arguments",
        "at",
        "call_id",
        "error",
        "item_id",
        "ok",
        "session_id",
        "task_id",
        "tool",
        "trust",
        "turn_id",
    }


async def test_the_widest_recall_trail_line_fits_one_log_driver_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    stored = [
        await recaller.record(f"note {number}", session_id="s1")
        for number in range(_HITS + _DROPPED)
    ]
    caplog.set_level(logging.INFO, logger="cortex.memory.recall")
    await LoggingRecallSink().record(
        RecallAudit(
            session_id=_WIDE,
            turn_id=_MINTED,
            query="q" * 4096,
            pool_size=_DROPPED,
            available=_DROPPED * 2,
            k=_HITS,
            ranking=Ranking(
                hits=tuple(
                    RankedMemory(
                        hit=ScoredMemory(record=held, score=_WIDEST_FLOAT), key=_WIDEST_FLOAT
                    )
                    for held in stored[:_HITS]
                ),
                basis=RankBasis.EMBER,
            ),
            dropped=DroppedCandidates(
                listed=tuple(
                    DroppedCandidate(id=held.id, score=_WIDEST_FLOAT) for held in stored[_HITS:]
                ),
                omitted=0,
            ),
            at=_AT,
        )
    )
    (record,) = caplog.records
    line = _line(record)
    assert len(line) < ONE_DOCKER_MESSAGE
    assert line.count(_MARKER) == 1
    assert set(record_fields(record)) == {
        "at",
        "available",
        "basis",
        "dropped",
        "dropped_omitted",
        "hits",
        "k",
        "keys_comparable",
        "pool",
        "query_chars",
        "session_id",
        "turn_id",
    }


async def test_the_widest_audit_gap_line_fits_one_log_driver_message(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    caplog.set_level(logging.WARNING, logger="cortex_tools.audit_file")
    await JsonLinesAuditSink(tmp_path).record(
        ToolInvocation(
            name=_WIDE,
            arguments={"instruction": _WIDE},
            ok=False,
            detail=_WIDE,
            at=_AT,
            trust=Trust.UNTRUSTED,
            call_id=_WIDE,
            session_id=_WIDE,
        )
    )
    (record,) = caplog.records
    assert record.getMessage() == "tool.audit.gap"
    assert "IsADirectoryError" in str(record.__dict__["error"])
    line = _line(record)
    assert len(line) < ONE_DOCKER_MESSAGE
    assert line.count(_MARKER) == 1
    assert set(record_fields(record)) == {"error", "path", "tool"}


async def test_the_widest_recall_gap_line_fits_one_log_driver_message(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    caplog.set_level(logging.WARNING, logger="cortex_memory.audit_file")
    await JsonLinesRecallSink(tmp_path).record(
        RecallAudit(
            session_id=_WIDE,
            turn_id=_WIDE,
            query=_WIDE,
            pool_size=0,
            available=0,
            k=_HITS,
            ranking=Ranking(hits=(), basis=RankBasis.EMBER),
            dropped=DroppedCandidates(listed=(), omitted=0),
            at=_AT,
        )
    )
    (record,) = caplog.records
    assert record.getMessage() == "memory.recall.gap"
    assert "IsADirectoryError" in str(record.__dict__["error"])
    line = _line(record)
    assert len(line) < ONE_DOCKER_MESSAGE
    assert line.count(_MARKER) == 1
    assert set(record_fields(record)) == {"error", "path", "turn_id"}


_MEASURED = frozenset(
    {LoggingAuditSink, LoggingRecallSink, JsonLinesAuditSink, JsonLinesRecallSink}
)
_WRITES_NO_LINE = {
    "TeeAuditSink": "records each invocation to the sinks it holds and logs nothing itself",
    "TeeRecallSink": "records each recall to the sinks it holds and logs nothing itself",
}

_SINK_PACKAGES = frozenset({"cortex_tools", "cortex_memory"})


def _wired_sinks() -> set[str]:
    """Every name ending in `Sink` that an orchestrator module imports from an adapter package."""
    root = Path(cortex_orchestrator.__file__).parent
    names: set[str] = set()
    for source in root.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if node.module.split(".")[0] in _SINK_PACKAGES:
                names |= {alias.name for alias in node.names if alias.name.endswith("Sink")}
    return names


def test_every_sink_the_orchestrator_wires_has_a_case_or_writes_no_line() -> None:
    wired = _wired_sinks()
    measured = {sink.__name__ for sink in _MEASURED}
    stale = set(_WRITES_NO_LINE) - wired
    assert not stale, f"exempted but no longer wired: {sorted(stale)}"
    assert not measured & set(_WRITES_NO_LINE)
    assert wired == measured | set(_WRITES_NO_LINE), (
        f"wired without a case or an exemption: {sorted(wired - measured - set(_WRITES_NO_LINE))}"
    )
