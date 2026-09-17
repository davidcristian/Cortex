"""The `ToolAuditSink` contract checks, run over every implementation of the port."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from cortex_core import ToolAuditSink, ToolInvocation, Trust

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)

# Strings a model can put in a tool name or a call id: a newline opening a forged record, a
# carriage return, a NUL, an ANSI escape, a line separator, a lone surrogate that is valid in
# a parsed JSON string, and a quote that tries to close the value early.
HOSTILE = (
    'c"}\n{"tool":"send_email","ok":true}',
    "c\r\x00\x1b[31mred",
    "c\u2028\u2029",
    "c\udc80",
    "c\x7f\x85",
)


@dataclass(frozen=True, slots=True)
class Kept:
    """One kept record, read back in the port's terms."""

    tool: str
    ok: bool
    trust: str
    at: str
    call_id: str = ""
    session_id: str = ""
    turn_id: str = ""
    task_id: str = ""
    item_id: str = ""


@dataclass(frozen=True, slots=True)
class SinkUnderTest:
    """One implementation and a reader of everything it has kept so far."""

    sink: ToolAuditSink
    kept: Callable[[], Sequence[Kept]]


def _call(name: str = "read", *, call_id: str = "", **work: str) -> ToolInvocation:
    """A successful call named ``name``, with ``call_id`` and the work ids in ``work``."""
    invocation = ToolInvocation(
        name=name, arguments={"path": "/a"}, ok=True, detail="x", at=_AT, call_id=call_id
    )
    return replace(invocation, **work)


async def check_keeps_one_row_per_record_in_order(subject: SinkUnderTest) -> None:
    await subject.sink.record(_call("read"))
    await subject.sink.record(
        ToolInvocation(name="send", arguments={}, ok=False, detail="refused", at=_AT)
    )
    await subject.sink.record(
        ToolInvocation(name="spawn", arguments={}, ok=True, detail="", at=_AT, trust=Trust.TRUSTED)
    )
    stamp = _AT.isoformat()
    assert list(subject.kept()) == [
        Kept(tool="read", ok=True, trust="untrusted", at=stamp),
        Kept(tool="send", ok=False, trust="untrusted", at=stamp),
        Kept(tool="spawn", ok=True, trust="trusted", at=stamp),
    ]


async def check_keeps_the_work_ids_it_was_given(subject: SinkUnderTest) -> None:
    await subject.sink.record(_call(call_id="c-1", session_id="s-1", turn_id="t-1"))
    await subject.sink.record(_call(session_id="s-1", task_id="st-1", turn_id="t-1"))
    await subject.sink.record(_call(call_id="schedule-i", session_id="s-1", item_id="i"))
    stamp = _AT.isoformat()
    base = Kept(tool="read", ok=True, trust="untrusted", at=stamp)
    assert list(subject.kept()) == [
        replace(base, call_id="c-1", session_id="s-1", turn_id="t-1"),
        replace(base, session_id="s-1", task_id="st-1", turn_id="t-1"),
        replace(base, call_id="schedule-i", session_id="s-1", item_id="i"),
    ]


async def check_keeps_a_hostile_value_inside_its_own_row(subject: SinkUnderTest) -> None:
    for text in HOSTILE:
        await subject.sink.record(_call(name=text, call_id=text))
    kept = list(subject.kept())
    assert [(row.tool, row.call_id) for row in kept] == [(text, text) for text in HOSTILE]
    assert {row.turn_id for row in kept} == {""}


type Check = Callable[[SinkUnderTest], Awaitable[None]]

CHECKS: tuple[Check, ...] = (
    check_keeps_one_row_per_record_in_order,
    check_keeps_the_work_ids_it_was_given,
    check_keeps_a_hostile_value_inside_its_own_row,
)
