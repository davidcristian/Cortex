from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta

from cortex_core import (
    REPEATED_LINE_NOTE,
    GenerationBounds,
    InferenceEvent,
    InMemorySessionStore,
    JsonSchema,
    Message,
    RepeatWatch,
    StopLedger,
    TextChunk,
    TextDelta,
    ToolSpec,
    TurnCompleted,
    TurnEngine,
)

_LINE = "Actually, I'll try `read_text_file` again."
_START = datetime(2026, 10, 14, 3, 0, tzinfo=UTC)


def test_a_line_arriving_the_third_time_is_a_repeat() -> None:
    watch = RepeatWatch()
    assert not watch.feed(f"{_LINE}\n{_LINE}\n")
    assert watch.feed(f"{_LINE}\n")


def test_a_line_split_across_pieces_counts_once_it_ends() -> None:
    watch = RepeatWatch()
    assert not watch.feed(f"{_LINE}\n{_LINE}\nActually, I'll try ")
    assert not watch.feed("`read_text_file` again.")
    assert watch.feed("\n")


def test_surrounding_spaces_do_not_make_a_line_new() -> None:
    watch = RepeatWatch()
    assert watch.feed(f"{_LINE}\n  {_LINE}\n{_LINE}  \n")


def test_a_short_line_never_repeats() -> None:
    watch = RepeatWatch()
    assert not watch.feed("Let me check.\n" * 5)


def test_a_line_without_a_letter_never_repeats() -> None:
    watch = RepeatWatch()
    assert not watch.feed("| --- | --- | --- | --- |\n" * 5)


def test_three_different_lines_are_no_repeat() -> None:
    watch = RepeatWatch()
    months = "".join(f"{m}: choir practice on the first Tuesday\n" for m in ("May", "June", "July"))
    assert not watch.feed(months * 2)


def test_a_ledger_that_saw_nothing_reports_no_repeat() -> None:
    assert not StopLedger().repeated


def test_a_reported_repeat_is_kept() -> None:
    ledger = StopLedger()
    ledger.observe_repeat()
    assert ledger.repeated


class _Clock:
    def __init__(self) -> None:
        self._ticks = 0

    def now(self) -> datetime:
        self._ticks += 1
        return _START + timedelta(seconds=self._ticks)


class _Looping:
    def __init__(self, chunks: Sequence[str]) -> None:
        self._chunks = chunks
        self.sent = 0
        self.closed = False

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        try:
            for chunk in self._chunks:
                self.sent += 1
                yield TextChunk(chunk)
        finally:
            self.closed = True


async def _reply(backend: _Looping, store: InMemorySessionStore) -> str:
    engine = TurnEngine(store, backend, _Clock())
    events = [event async for event in engine.handle_turn("s", "who sings?", turn_id="t-1")]
    shown = "".join(event.text for event in events if isinstance(event, TextDelta))
    completed = events[-1]
    assert isinstance(completed, TurnCompleted)
    assert completed.full_text == shown
    return shown


async def test_a_reply_repeating_one_line_ends_there_with_the_note_it_stores() -> None:
    store = InMemorySessionStore()
    backend = _Looping(["The file did not open.\n", *([f"{_LINE}\n"] * 6), "never read"])
    shown = await _reply(backend, store)
    assert shown == "The file did not open.\n" + f"{_LINE}\n" * 3 + REPEATED_LINE_NOTE
    assert (await store.history("s"))[-1].text == shown
    assert backend.sent == 4
    assert backend.closed


async def test_a_reply_whose_lines_differ_runs_to_its_end_with_no_note() -> None:
    store = InMemorySessionStore()
    lines = [f"Week {n}: the altos sing the second verse.\n" for n in range(1, 6)]
    backend = _Looping(lines)
    assert await _reply(backend, store) == "".join(lines)
    assert backend.sent == 5
