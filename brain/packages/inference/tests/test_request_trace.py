from datetime import UTC, datetime
from typing import cast

import pytest

from cortex_core import GenerationBounds, Message, Role, ToolCall
from cortex_inference.request import TRACE_KEY, build_payload, to_openai_message

_AT = datetime(2026, 11, 28, 12, 0, tzinfo=UTC)
_CALL = ToolCall(id="c1", name="list_scheduled", arguments={})


def _call(trace: str) -> Message:
    return Message(
        role=Role.ASSISTANT,
        text="One moment.",
        at=_AT,
        turn_id="t",
        tool_calls=(_CALL,),
        trace=trace,
    )


def _turn(trace: str) -> list[Message]:
    return [
        Message(role=Role.USER, text="List my reminders.", at=_AT, turn_id="t"),
        _call(trace),
        Message(role=Role.TOOL, text="none", at=_AT, turn_id="t", tool_call_id="c1"),
    ]


def test_the_wire_name_is_the_one_llama_cpp_hands_a_chat_template() -> None:
    assert TRACE_KEY == "reasoning_content"


def test_a_call_message_asked_to_send_its_trace_renders_it_beside_its_calls() -> None:
    rendered = to_openai_message(_call("List first."), trace=True)
    assert rendered["reasoning_content"] == "List first."
    assert rendered["content"] == "One moment."
    assert rendered["tool_calls"] == [
        {"id": "c1", "type": "function", "function": {"name": "list_scheduled", "arguments": "{}"}}
    ]


def test_a_call_message_renders_no_trace_unless_asked() -> None:
    assert TRACE_KEY not in to_openai_message(_call("List first."))


def test_an_empty_trace_renders_no_field_even_when_asked() -> None:
    assert TRACE_KEY not in to_openai_message(_call(""), trace=True)


def test_a_request_whose_bounds_resend_the_trace_sends_it_on_the_call_message() -> None:
    payload = build_payload(
        "m", _turn("List first."), (), None, GenerationBounds(resend_trace=True)
    )
    sent = cast("list[dict[str, object]]", payload["messages"])
    assert [message.get(TRACE_KEY) for message in sent] == [None, "List first.", None]


@pytest.mark.parametrize("bounds", [None, GenerationBounds(), GenerationBounds(thinking=False)])
def test_a_request_that_does_not_ask_sends_what_it_sent_before_the_field(
    bounds: GenerationBounds | None,
) -> None:
    with_trace = build_payload("m", _turn("List first."), (), None, bounds)
    without = build_payload("m", _turn(""), (), None, bounds)
    assert with_trace == without
