"""Behavior tests for the conversation domain: roles, immutability, tz-awareness."""

import dataclasses
from datetime import UTC, datetime, timedelta, timezone, tzinfo

import pytest

from cortex_core import ImagePart, Message, Role, ToolCall

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


def test_a_tool_message_may_carry_images() -> None:
    picture = ImagePart(data=b"\x89PNG", mime_type="image/png", width=8, height=8)
    message = Message(
        role=Role.TOOL, text="capture", at=_AT, turn_id="t1", tool_call_id="c1", images=(picture,)
    )
    assert message.images == (picture,)


@pytest.mark.parametrize("role", [Role.USER, Role.ASSISTANT, Role.SYSTEM])
def test_no_role_but_tool_may_carry_images(role: Role) -> None:
    """Pixels are turn-local, and they ride the tool result they arrived on.

    The invariant lives on the value so it holds even for a code path that never touches a store,
    and it is checked before any store is asked to refuse it. SYSTEM is refused for a second
    reason: it is never persisted, so turn-locality alone would allow it, but the inference
    adapter builds a content-parts array for a tool message only and emits the plain string for
    every other role. An image on a SYSTEM message would be dropped on the way to the model
    without a word, so the domain refuses to express it rather than the adapter discarding it.
    """
    picture = ImagePart(data=b"\x89PNG", mime_type="image/png", width=8, height=8)
    with pytest.raises(ValueError, match="may not carry images: pixels are turn-local"):
        Message(role=role, text="hi", at=_AT, turn_id="t1", images=(picture,))


def test_an_image_free_persistable_message_is_untouched() -> None:
    assert Message(role=Role.USER, text="hi", at=_AT, turn_id="t1").images == ()
