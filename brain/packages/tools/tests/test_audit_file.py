import json
import logging
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest
from audit_contract import HOSTILE

from cortex_core import (
    CUT,
    REDACTED,
    VALUE_CHARS,
    RecordingAuditSink,
    ToolInvocation,
    record_fields,
    render_value,
)
from cortex_tools import (
    JsonLinesAuditSink,
    TeeAuditSink,
    durable_line,
    durable_value,
    invocation_fields,
)

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


def _call(arguments: object = None, *, call_id: str = "", turn_id: str = "") -> ToolInvocation:
    return ToolInvocation(
        name="read",
        arguments={} if arguments is None else {"value": arguments},
        ok=True,
        detail="secret file content",
        at=_AT,
        call_id=call_id,
        turn_id=turn_id,
    )


def _rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines()]


def _stored(arguments: object) -> object:
    """What the file keeps under `arguments` for a call whose one argument is ``arguments``."""
    return json.loads(durable_line(_call(arguments)))["arguments"]


def test_a_record_holds_the_fields_the_log_line_holds() -> None:
    call = _call("/etc/hosts", call_id="c-1", turn_id="t-1")
    assert json.loads(durable_line(call)) == invocation_fields(call)
    assert json.loads(durable_line(call)) == {
        "arguments": {"value": "/etc/hosts"},
        "at": "2026-07-03T12:00:00+00:00",
        "call_id": "c-1",
        "ok": True,
        "result_chars": 19,
        "tool": "read",
        "trust": "untrusted",
        "turn_id": "t-1",
    }


def test_a_url_credential_is_withheld_as_the_line_withholds_it() -> None:
    assert _stored("redis://:pw@redis:6379") == {"value": f"redis://{REDACTED}@redis:6379"}
    assert _stored({"http://u:pw@key": 1}) == {"value": {f"http://{REDACTED}@key": 1}}
    row = json.loads(durable_line(_call(call_id="http://u:pw@host")))
    assert row["call_id"] == f"http://{REDACTED}@host"


def test_a_credential_split_across_two_strings_keeps_the_lines_own_text() -> None:
    arguments = ["http://user:pw", "@host"]
    stored = _stored(arguments)
    assert stored == render_value({"value": arguments})
    assert isinstance(stored, str)
    assert "pw" not in stored


def test_a_value_the_line_cuts_is_kept_as_the_lines_cut_text() -> None:
    long = "a" * (VALUE_CHARS * 2)
    stored = _stored(long)
    assert stored == render_value({"value": long})
    assert isinstance(stored, str)
    assert stored.endswith(CUT.format(chars=VALUE_CHARS + 12))
    row = json.loads(durable_line(_call(call_id=long)))
    assert row["call_id"] == render_value(long)
    assert len(row["call_id"]) < VALUE_CHARS * 2


def test_a_secret_named_argument_is_withheld_as_the_line_withholds_it() -> None:
    arguments = {"password": "hunter2", "items": [{"api_token": "abc", "path": "/a"}]}
    call = ToolInvocation(
        name="read", arguments=arguments, ok=True, detail="", at=_AT, call_id="c-1"
    )
    row = json.loads(durable_line(call))
    assert row["arguments"] == {
        "items": [{"api_token": REDACTED, "path": "/a"}],
        "password": REDACTED,
    }
    record = logging.LogRecord("cortex.tools.audit", logging.INFO, "p.py", 1, "m", (), None)
    record.__dict__.update(invocation_fields(call))
    assert row == record_fields(record)


def test_a_structure_too_deep_to_walk_is_kept_withheld_rather_than_as_a_gap() -> None:
    assert _stored(_nested(100_000)) == REDACTED


def test_a_non_finite_number_is_kept_as_the_lines_text() -> None:
    assert _stored(float("nan")) == '{"value":NaN}'
    assert _stored([float("inf")]) == '{"value":[Infinity]}'


def test_scalars_and_short_structures_are_kept_as_values() -> None:
    assert durable_value(value=True) is True
    assert durable_value(7) == 7
    assert durable_value("plain") == "plain"
    assert durable_value("two words") == "two words"
    assert _stored((1, 2.5, None, "x")) == {"value": [1, 2.5, None, "x"]}
    assert _stored({1, 2} - {2}) == {"value": "{1}"}


def test_every_record_is_one_line_of_printable_ascii() -> None:
    for text in (*HOSTILE, "\x00" * 50, "\u0085\u2028\ufeff"):
        line = durable_line(_call(text, call_id=text))
        assert line.endswith(b"\n")
        assert line.count(b"\n") == 1
        assert all(0x20 <= byte < 0x80 for byte in line[:-1])


async def test_records_are_appended_one_per_line(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    sink = JsonLinesAuditSink(path)
    await sink.record(_call(turn_id="t-1"))
    await sink.record(_call(turn_id="t-2"))
    assert [row["turn_id"] for row in _rows(path)] == ["t-1", "t-2"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


async def test_a_torn_last_line_is_closed_before_the_next_record(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_bytes(b'{"tool":"re')
    await JsonLinesAuditSink(path).record(_call(turn_id="t-1"))
    torn, line = path.read_bytes().split(b"\n", 1)
    assert torn == b'{"tool":"re'
    assert json.loads(line)["turn_id"] == "t-1"
    assert line.count(b"\n") == 1


async def test_a_file_moved_away_is_created_again(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    sink = JsonLinesAuditSink(path)
    await sink.record(_call(turn_id="t-1"))
    path.rename(tmp_path / "audit.jsonl.1")
    await sink.record(_call(turn_id="t-2"))
    assert [row["turn_id"] for row in _rows(path)] == ["t-2"]


def _nested(depth: int) -> object:
    value: object = []
    for _ in range(depth):
        value = [value]
    return value


class _EndlessText:
    """An argument whose text never finishes, which no structure walk can see coming."""

    def __str__(self) -> str:
        return str(self)


def _cycle() -> object:
    looped: list[object] = []
    looped.append(looped)
    return looped


@pytest.mark.parametrize(
    ("arguments", "error"),
    [
        ({("a", "b"): 1}, "TypeError: keys must be str"),
        (_cycle(), "ValueError: Circular reference detected"),
        (_EndlessText(), "RecursionError: maximum recursion depth exceeded"),
    ],
    ids=["tuple-key", "cycle", "endless-text"],
)
async def test_an_unrenderable_argument_is_a_gap_not_a_failure(
    arguments: object, error: str, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "audit.jsonl"
    await JsonLinesAuditSink(path).record(_call(arguments))
    assert not path.exists()
    (record,) = caplog.records
    assert (record.levelno, record.name, record.getMessage()) == (
        logging.WARNING,
        "cortex_tools.audit_file",
        "tool.audit.gap",
    )
    assert str(record.__dict__["error"]).startswith(error)


async def test_a_refused_append_is_a_gap_naming_the_file_and_the_tool(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "missing" / "audit.jsonl"
    await JsonLinesAuditSink(path).record(_call("x"))
    (record,) = caplog.records
    fields = record.__dict__
    assert (fields["path"], fields["tool"]) == (str(path), "read")
    assert str(fields["error"]).startswith("FileNotFoundError: [Errno 2]")
    assert "secret file content" not in str(fields)


async def test_the_tee_records_to_each_sink_in_order() -> None:
    order: list[str] = []

    class Labelled(RecordingAuditSink):
        def __init__(self, label: str) -> None:
            super().__init__()
            self.label = label

        async def record(self, invocation: ToolInvocation) -> None:
            order.append(self.label)
            await super().record(invocation)

    first, second = Labelled("first"), Labelled("second")
    await TeeAuditSink((first, second)).record(_call())
    assert order == ["first", "second"]
    assert first.records == second.records == (_call(),)
