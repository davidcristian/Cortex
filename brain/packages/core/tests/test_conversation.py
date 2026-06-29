"""Behavior tests for the conversation domain: roles, immutability, tz-awareness."""

import dataclasses
from datetime import UTC, datetime, timedelta, timezone, tzinfo

import pytest

from cortex_core import Message, Role, ToolCall

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


class _OffsetlessTzinfo(tzinfo):
    """A pathological tzinfo that claims no UTC offset (still a naive datetime)."""

    def utcoffset(self, dt: datetime | None) -> timedelta | None:
        del dt
        return None


@pytest.mark.parametrize(
    ("role", "value"),
    [
        (Role.USER, "user"),
        (Role.ASSISTANT, "assistant"),
        (Role.SYSTEM, "system"),
        (Role.TOOL, "tool"),
    ],
)
def test_role_values_are_stable_strings(role: Role, value: str) -> None:
    assert role.value == value


def test_message_carries_all_fields() -> None:
    message = Message(role=Role.USER, text="hi", at=_AT, turn_id="t-1")
    assert (message.role, message.text, message.at, message.turn_id) == (
        Role.USER,
        "hi",
        _AT,
        "t-1",
    )
    # Tool fields default empty for ordinary dialogue.
    assert (message.tool_calls, message.tool_call_id) == ((), None)


def test_message_carries_tool_call_structure() -> None:
    call = ToolCall(id="c1", name="read", arguments={"path": "/x"})
    assistant = Message(role=Role.ASSISTANT, text="", at=_AT, turn_id="t-1", tool_calls=(call,))
    result = Message(role=Role.TOOL, text="body", at=_AT, turn_id="t-1", tool_call_id="c1")
    assert assistant.tool_calls == (call,)
    assert (result.tool_call_id, result.text) == ("c1", "body")


def test_message_is_immutable() -> None:
    message = Message(role=Role.USER, text="hi", at=_AT, turn_id="t-1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        message.text = "rewritten"  # pyright: ignore[reportAttributeAccessIssue]


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Message(role=Role.USER, text="hi", at=datetime(2026, 7, 3, 12, 0, 0), turn_id="t")  # noqa: DTZ001


def test_offsetless_tzinfo_is_rejected() -> None:
    at = datetime(2026, 7, 3, 12, 0, 0, tzinfo=_OffsetlessTzinfo())
    with pytest.raises(ValueError, match="timezone-aware"):
        Message(role=Role.USER, text="hi", at=at, turn_id="t")


def test_non_utc_timezone_is_accepted() -> None:
    at = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    message = Message(role=Role.ASSISTANT, text="ok", at=at, turn_id="t-2")
    assert message.at.utcoffset() == timedelta(hours=5, minutes=30)
