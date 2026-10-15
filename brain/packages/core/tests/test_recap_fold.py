from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

from cortex_core import (
    CharBudgetHistoryWindow,
    InMemorySessionStore,
    Message,
    Role,
    SummarizingHistoryWindow,
    TextChunk,
    ToolSpec,
)
from cortex_core.inference import GenerationBounds, InferenceEvent, JsonSchema
from cortex_core.recap_prompt import RECAP_READ_MAX, fold_slice

_AT = datetime(2026, 10, 15, 3, 0, tzinfo=UTC)


class _FixedClock:
    def now(self) -> datetime:
        return _AT


class _RecordingBackend:
    """Replies with one fixed account and keeps each prompt's last message."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema, bounds
        self.prompts.append(messages[-1].text)
        yield TextChunk(f"Account {len(self.prompts)}.")


def _message(role: Role, text: str, turn_id: str) -> Message:
    return Message(role=role, text=text, at=_AT, turn_id=turn_id)


def test_messages_that_fit_the_limit_are_all_read_whole() -> None:
    dropped = [_message(Role.USER, "a" * 40, "t-1"), _message(Role.ASSISTANT, "b" * 60, "t-1")]

    assert fold_slice(dropped, 100) == dropped


def test_the_slice_ends_before_the_first_message_that_does_not_fit() -> None:
    dropped = [
        _message(Role.USER, "a" * 40, "t-1"),
        _message(Role.ASSISTANT, "b" * 70, "t-1"),
        _message(Role.USER, "c" * 10, "t-2"),
    ]

    assert fold_slice(dropped, 100) == dropped[:1]


def test_a_first_message_past_the_limit_keeps_its_head_and_tail_around_the_cut() -> None:
    text = "H" * 100 + "M" * 100 + "T" * 51
    (cut,) = fold_slice([_message(Role.USER, text, "t-1"), _message(Role.USER, "x", "t-2")], 101)

    assert cut.text == (
        "H" * 75
        + "\n[150 characters from the middle of this message were cut here and were not read.]\n"
        + "T" * 26
    )
    assert (cut.role, cut.turn_id) == (Role.USER, "t-1")


async def test_a_dropped_paste_past_the_limit_is_folded_from_its_head_and_covered() -> None:
    store = InMemorySessionStore()
    backend = _RecordingBackend()
    window = SummarizingHistoryWindow(
        CharBudgetHistoryWindow(100), store, backend, "cortex", _FixedClock()
    )
    paste = "A" * (RECAP_READ_MAX * 2) + "Z" * RECAP_READ_MAX
    history = [
        _message(Role.USER, paste, "t-1"),
        _message(Role.ASSISTANT, "(too long)", "t-1"),
        _message(Role.USER, "lemon?", "t-2"),
    ]

    await window.select(history, session_id="s")

    (prompt,) = backend.prompts
    assert "A" * 12_000 + "\n[32000 characters from the middle" in prompt
    assert "A" * 12_001 not in prompt
    assert "were not read.]\n" + "Z" * 4_000 in prompt
    assert "Z" * 4_001 not in prompt
    recap = await store.recap("s")
    assert recap is not None
    assert recap.covers == 1


async def test_a_dropped_run_past_the_limit_is_folded_over_the_next_turns() -> None:
    store = InMemorySessionStore()
    backend = _RecordingBackend()
    window = SummarizingHistoryWindow(
        CharBudgetHistoryWindow(10), store, backend, "cortex", _FixedClock()
    )
    half = "h" * (RECAP_READ_MAX // 2 + 1)
    history = [
        _message(Role.USER, half, "t-1"),
        _message(Role.ASSISTANT, half, "t-1"),
        _message(Role.USER, "next", "t-2"),
    ]

    first = await window.select(history, session_id="s")
    second = await window.select(history, session_id="s")

    assert [recap.covers for recap in [await store.recap("s")] if recap is not None] == [2]
    assert len(backend.prompts) == 2
    assert "Account 1." in backend.prompts[1]
    assert "Account 1." in first[0].text
    assert "Account 2." in second[0].text
