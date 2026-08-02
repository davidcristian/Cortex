"""Behavior of the pure session-summary derivation and title generation (ADR-0021)."""

from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    InferenceError,
    Message,
    ReasoningChunk,
    Role,
    SessionSummary,
    TextChunk,
    ToolCall,
    ToolSpec,
    build_title_messages,
    clean_title,
    generate_title,
    summarize_session,
)
from cortex_core.inference import InferenceEvent, JsonSchema
from cortex_core.sessions import PREVIEW_MAX, TITLE_MAX

_EARLY = datetime(2026, 7, 8, 9, 0, tzinfo=UTC)
_LATE = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)


def _msg(role: Role, text: str, at: datetime) -> Message:
    return Message(role=role, text=text, at=at, turn_id="t")


def test_title_is_the_first_message_and_preview_is_the_last() -> None:
    summary = summarize_session(
        "s1",
        [
            _msg(Role.USER, "what is a cortex", _EARLY),
            _msg(Role.ASSISTANT, "a resident model", _LATE),
        ],
    )
    assert summary == SessionSummary(
        session_id="s1",
        title="what is a cortex",
        preview="a resident model",
        last_activity=_LATE,
    )


def test_single_message_session_uses_it_for_both_title_and_preview() -> None:
    summary = summarize_session("s1", [_msg(Role.USER, "lone question", _EARLY)])
    assert summary.title == "lone question"
    assert summary.preview == "lone question"
    assert summary.last_activity == _EARLY


def test_the_title_bound_is_forty_eight_characters() -> None:
    # The overlay's `sessionState.ts` declares the same number for the live title it derives
    # before a chat is listed, so the header and that chat's own switcher row cut at the same
    # place. Pinned to the literal rather than to itself: an assertion that `TITLE_MAX ==
    # TITLE_MAX` stays green while the two halves drift, which is what they did (48 here
    # against 32 there) until crosscheck.py tied them.
    assert TITLE_MAX == 48


def test_whitespace_is_collapsed_to_single_spaces() -> None:
    summary = summarize_session("s1", [_msg(Role.USER, "  hello \n\t world  ", _EARLY)])
    assert summary.title == "hello world"


def test_long_title_and_preview_are_truncated_with_an_ellipsis() -> None:
    long_title = "T" * (TITLE_MAX + 20)
    long_preview = "P" * (PREVIEW_MAX + 20)
    summary = summarize_session(
        "s1",
        [_msg(Role.USER, long_title, _EARLY), _msg(Role.ASSISTANT, long_preview, _LATE)],
    )
    assert summary.title == "T" * TITLE_MAX + "…"
    assert summary.preview == "P" * PREVIEW_MAX + "…"


def test_title_exactly_at_the_limit_is_not_truncated() -> None:
    exact = "E" * TITLE_MAX
    summary = summarize_session("s1", [_msg(Role.USER, exact, _EARLY)])
    assert summary.title == exact


def test_a_title_override_replaces_the_first_message_title_but_not_the_preview() -> None:
    summary = summarize_session(
        "s1",
        [_msg(Role.USER, "what is a cortex", _EARLY), _msg(Role.ASSISTANT, "a model", _LATE)],
        title_override="Cortex basics",
    )
    assert summary.title == "Cortex basics"
    assert summary.preview == "a model"  # preview stays derived from the last message


def test_a_blank_or_whitespace_override_falls_back_to_the_first_message() -> None:
    messages = [_msg(Role.USER, "the opening line", _EARLY)]
    assert summarize_session("s1", messages, title_override="").title == "the opening line"
    assert summarize_session("s1", messages, title_override="   ").title == "the opening line"


def test_an_oversize_override_is_collapsed_and_truncated_like_a_derived_title() -> None:
    summary = summarize_session(
        "s1",
        [_msg(Role.USER, "short first", _EARLY)],
        title_override="O" * (TITLE_MAX + 20),
    )
    assert summary.title == "O" * TITLE_MAX + "…"


def test_build_title_messages_is_one_user_message_with_the_opening_exchange() -> None:
    (message,) = build_title_messages(
        "what is a cortex", "a resident model", at=_EARLY, turn_id="t"
    )
    assert message.role is Role.USER
    assert message.at == _EARLY
    assert message.turn_id == "t"
    assert "User: what is a cortex" in message.text
    assert "Assistant: a resident model" in message.text


def test_clean_title_collapses_whitespace_strips_quotes_and_bounds_the_length() -> None:
    assert clean_title('  "A  Nice\nTitle"  ') == "A Nice Title"
    assert clean_title("plain title") == "plain title"
    assert clean_title("W" * (TITLE_MAX + 5)) == "W" * TITLE_MAX
    assert clean_title("   \n\t  ") == ""  # nothing usable comes back empty for the caller


class _ScriptedBackend:
    """InferenceBackend that yields a fixed event sequence, or raises before yielding."""

    def __init__(
        self, events: Sequence[InferenceEvent], *, fail: InferenceError | None = None
    ) -> None:
        self._events = events
        self._fail = fail

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema
        if self._fail is not None:
            raise self._fail
        for event in self._events:
            yield event


async def test_generate_title_accumulates_only_the_reply_text() -> None:
    backend = _ScriptedBackend(
        [
            ReasoningChunk("let me think about a good title"),
            TextChunk("Cat sleep "),
            ToolCall(id="c1", name="noop", arguments={}),
            TextChunk("habits"),
        ]
    )
    assert await generate_title(backend, "cortex", []) == "Cat sleep habits"


async def test_generate_title_of_an_empty_reply_is_empty() -> None:
    backend = _ScriptedBackend([ReasoningChunk("thinking, no reply text")])
    assert await generate_title(backend, "cortex", []) == ""


async def test_generate_title_propagates_an_inference_error() -> None:
    backend = _ScriptedBackend([], fail=InferenceError("model down"))
    with pytest.raises(InferenceError, match="model down"):
        await generate_title(backend, "cortex", [])
