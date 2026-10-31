from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    GenerationBounds,
    InferenceError,
    InferenceEvent,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    ReasoningChunk,
    RecordingAuditSink,
    Role,
    TaintLedger,
    TextChunk,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnCompleted,
    TurnEngine,
)
from cortex_core.loop_events import ReasoningDelta, StepOutcome, ToolStep
from cortex_core.round_opening import OpeningHold
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 10, 30, 3, 0, 0, tzinfo=UTC)
_ANSWER = "The capital of Australia is Canberra."
_READ = ToolCall(id="c1", name="read", arguments={})


class _Clock:
    def __init__(self) -> None:
        self._ticks = 0

    def now(self) -> datetime:
        self._ticks += 1
        return _AT + timedelta(seconds=self._ticks)


class _Rounds:
    """Streams one scripted round per request; a round of ``None`` raises after its chunks."""

    def __init__(self, rounds: Sequence[Sequence[InferenceEvent | None]]) -> None:
        self._rounds = list(rounds)
        self.closed = 0
        self.seen: list[Sequence[Message]] = []

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
        self.seen.append(list(messages))
        try:
            for event in self._rounds.pop(0):
                if event is None:
                    msg = "the engine stopped"
                    raise InferenceError(msg)
                yield event
        finally:
            self.closed += 1


async def _read(arguments: Mapping[str, object]) -> str:
    del arguments
    return "nothing was forgotten"


def _context() -> ToolLoopContext:
    registry = InMemoryToolRegistry({"read": (ToolSpec("read", "read", {}), _read)})
    return ToolLoopContext(
        dispatcher=ToolDispatcher(registry, RecordingAuditSink(), _Clock()),
        clock=_Clock(),
        turn_id="t-1",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
    )


async def _texts(backend: _Rounds) -> list[str]:
    working = [Message(role=Role.USER, text="capital?", at=_AT, turn_id="t-1")]
    loop = stream_tool_loop(backend, "m", working, _context())
    return [piece async for piece in loop if isinstance(piece, str)]


def _chunks(*texts: str) -> list[InferenceEvent]:
    return [TextChunk(text) for text in texts]


@pytest.mark.parametrize(
    ("second", "shown"),
    [
        (["The capital of Australia is Canberra. I've also checked."], "I've also checked."),
        (
            ["The capital ", "of Australia is Canberra.", " I've", " also checked."],
            "I've also checked.",
        ),
        ([_ANSWER], ""),
        ([_ANSWER, "\n\n"], ""),
        (["\n\n", _ANSWER, "\nDone."], "\n\nDone."),
        (["I checked. ", _ANSWER], "I checked. " + _ANSWER),
        (
            ["The capital of Australia is Canberra, a planned city."],
            "The capital of Australia is Canberra, a planned city.",
        ),
        (
            ["the capital of Australia is Canberra. Done."],
            "the capital of Australia is Canberra. Done.",
        ),
        (["Done."], "Done."),
    ],
)
async def test_a_round_drops_only_an_opening_sentence_an_earlier_round_wrote(
    *, second: list[str], shown: str
) -> None:
    backend = _Rounds([[*_chunks(_ANSWER, "\n\n"), _READ], _chunks(*second)])
    assert "".join(await _texts(backend)) == f"{_ANSWER}\n\n{shown}"


async def test_a_dropped_sentence_keeps_the_space_after_it_when_none_was_before() -> None:
    backend = _Rounds([[*_chunks(_ANSWER), _READ], _chunks(_ANSWER, " Done.")])
    assert "".join(await _texts(backend)) == f"{_ANSWER} Done."


_SECOND = "I removed the number from my memory."
_TWO = f"{_ANSWER} {_SECOND}"


@pytest.mark.parametrize(
    ("second", "shown"),
    [
        ([f"{_TWO} Done."], "Done."),
        ([f"{_SECOND} {_ANSWER} Done."], "Done."),
        ([_ANSWER, " I removed the ", "number from my memory.", "\n\nDone."], "Done."),
        ([_TWO], ""),
        ([_TWO, "\n"], ""),
        (["\n\n", _TWO, "\nDone."], "\n\nDone."),
        ([f"{_ANSWER} Then I checked. {_SECOND}"], f"Then I checked. {_SECOND}"),
        ([f"{_ANSWER} Then I checked. {_ANSWER}"], f"Then I checked. {_ANSWER}"),
        ([f"Then I checked. {_TWO}"], f"Then I checked. {_TWO}"),
        ([f"{_ANSWER} I removed the number. {_SECOND}"], f"I removed the number. {_SECOND}"),
        ([f"{_ANSWER} Then I"], "Then I"),
    ],
)
async def test_a_round_drops_each_opening_sentence_up_to_the_first_new_one(
    *, second: list[str], shown: str
) -> None:
    backend = _Rounds([[*_chunks(_TWO, "\n\n"), _READ], _chunks(*second)])
    assert "".join(await _texts(backend)) == f"{_TWO}\n\n{shown}"


async def test_two_dropped_sentences_keep_one_gap_when_none_was_before() -> None:
    backend = _Rounds([[*_chunks(_TWO), _READ], _chunks(f"{_TWO}  Done.")])
    assert "".join(await _texts(backend)) == f"{_TWO} Done."


async def test_a_round_holding_a_later_sentence_shows_it_before_the_engine_failure() -> None:
    backend = _Rounds([[*_chunks(_TWO), _READ], [*_chunks(f"{_TWO} Then I"), None]])
    assert await _until_failure(backend) == [_TWO, " Then I"]


def test_the_text_stays_held_until_a_new_sentence_begins_then_each_chunk_streams() -> None:
    hold = OpeningHold(_TWO)
    assert hold.feed(f"{_ANSWER} ") == ""
    assert hold.feed(_SECOND) == ""
    assert hold.feed(" Then") == ""
    assert hold.feed(" I checked.") == ""
    assert hold.feed(" Done") == " Then I checked. Done"
    assert hold.feed(".") == "."
    assert hold.flush() == ""


def test_a_list_item_after_a_dropped_line_is_kept() -> None:
    hold = OpeningHold("Results:\n- Done.\n")
    assert hold.feed("Results:\n- Done.\n- Saved.") == "- Done.\n- Saved."


async def test_a_round_after_one_with_no_text_streams_each_chunk_as_it_comes() -> None:
    backend = _Rounds([[_READ], _chunks("The capital ", "is ", "Canberra.")])
    assert await _texts(backend) == ["The capital ", "is ", "Canberra."]


async def test_the_next_request_holds_the_text_the_person_saw() -> None:
    second = [*_chunks(_ANSWER, " I read it."), _READ]
    backend = _Rounds([[*_chunks(_ANSWER), _READ], second, _chunks("Done.")])
    assert "".join(await _texts(backend)) == f"{_ANSWER} I read it.Done."
    calls = [m.text for m in backend.seen[2] if m.tool_calls]
    assert calls == [_ANSWER, " I read it."]


async def _until_failure(backend: _Rounds) -> list[str]:
    working = [Message(role=Role.USER, text="capital?", at=_AT, turn_id="t-1")]
    texts: list[str] = []
    try:
        async for piece in stream_tool_loop(backend, "m", working, _context()):
            texts.extend([piece] if isinstance(piece, str) else [])
    except InferenceError:
        return texts
    msg = "the loop ended without the engine failure"
    raise AssertionError(msg)


async def test_a_held_opening_is_shown_before_the_engine_failure() -> None:
    backend = _Rounds([[*_chunks(_ANSWER), _READ], [*_chunks("Then I"), None]])
    assert await _until_failure(backend) == [_ANSWER, "Then I"]
    assert backend.closed == 2


async def test_a_failure_with_nothing_held_shows_nothing_more() -> None:
    backend = _Rounds([[*_chunks(_ANSWER), _READ], [None]])
    with pytest.raises(InferenceError):
        await _texts(backend)


async def test_closing_the_loop_while_a_sentence_is_held_closes_the_engine_stream() -> None:
    second = [TextChunk("Then I"), ReasoningChunk("thinking"), TextChunk(" read it. More.")]
    backend = _Rounds([[*_chunks(_ANSWER), _READ], second])
    working = [Message(role=Role.USER, text="capital?", at=_AT, turn_id="t-1")]
    loop = stream_tool_loop(backend, "m", working, _context())
    texts = [piece async for piece in _until_reasoning(loop)]
    await loop.aclose()
    assert texts == [_ANSWER]
    assert backend.closed == 2


async def _until_reasoning(
    loop: AsyncIterator[str | ReasoningDelta | ToolStep | StepOutcome],
) -> AsyncIterator[str]:
    async for piece in loop:
        if isinstance(piece, ReasoningDelta):
            return
        if isinstance(piece, str):
            yield piece


def test_a_hold_with_no_earlier_text_holds_nothing() -> None:
    hold = OpeningHold("  \n")
    assert hold.feed("Hi") == "Hi"
    assert hold.flush() == ""


@pytest.mark.parametrize(
    ("said", "text"),
    [
        ("The first results:\n1. Berlin is sunny.\n", "1. Paris is rainy.\n2. Rome is warm."),
        ("The first file:\n```\nalpha\n```\n", "```\nbeta\n```\nThat is the second."),
        ("The first file:\n```\nalpha\n```\n", "```"),
    ],
)
def test_a_list_number_or_code_fence_an_earlier_round_wrote_is_kept(said: str, text: str) -> None:
    hold = OpeningHold(said)
    assert "".join(hold.feed(char) for char in text) + hold.flush() == text


@pytest.mark.parametrize(
    ("said", "text"),
    [
        ("The first file:\n```python\nprint(1)\n```\n", "```python\nprint(2)\n```"),
        ("| Name | Value |\n| --- | --- |\n| a | 1 |\n", "| Name | Value |\n| --- | --- |"),
        ("Here are the steps:\n## Steps\n1. Open it.\n", "## Steps\n1. Close it."),
        ("Status:\n- Done.\n", "- Done.\n- Saved."),
        ("Results:\n1) Berlin is sunny.\n", "1) Berlin is sunny.\n2) Rome is warm."),
        ("> Quote me.\n", "> Quote me.\nThat was it."),
    ],
)
def test_a_heading_table_row_list_item_or_quote_an_earlier_round_wrote_is_kept(
    said: str, text: str
) -> None:
    hold = OpeningHold(said)
    assert "".join(hold.feed(char) for char in text) + hold.flush() == text


@pytest.mark.parametrize("said", ["#hashtag fun.\n", "-5 degrees today.\n"])
def test_a_sentence_opening_with_a_mark_but_no_structure_is_dropped(said: str) -> None:
    hold = OpeningHold(said)
    assert hold.feed(said + "It is cold.") + hold.flush() == "It is cold."


async def test_the_stored_reply_holds_the_repeated_sentence_once() -> None:
    backend = _Rounds([[*_chunks(_ANSWER, "\n\n"), _READ], _chunks(_ANSWER, " I checked.")])
    registry = InMemoryToolRegistry({"read": (ToolSpec("read", "read", {}), _read)})
    caps = TurnCapabilities(tools=ToolDispatcher(registry, RecordingAuditSink(), _Clock()))
    sessions = InMemorySessionStore()
    engine = TurnEngine(sessions, backend, _Clock(), capabilities=caps)
    events = [e async for e in engine.handle_turn("s", "capital?", turn_id="t-1")]
    shown = "".join(event.text for event in events if isinstance(event, TextDelta))
    assert shown == f"{_ANSWER}\n\nI checked."
    assert events[-1] == TurnCompleted(turn_id="t-1", full_text=shown)
    assert (await sessions.history("s"))[-1].text == shown
