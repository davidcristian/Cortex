from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta

import pytest

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
_ASKED = "Remember to bring your sheet music to practice."
_ASK = f"Write the sentence '{_ASKED}' ten times, one per line."
_NAMED = f"Write the sentence '{_ASKED}' on every line."
_MADE_UP = "Make up one sentence of advice for a choir singer, then write it ten times."
_START = datetime(2026, 10, 14, 3, 0, tzinfo=UTC)


def test_a_line_three_times_back_to_back_is_a_repeat() -> None:
    watch = RepeatWatch("who sings?")
    assert not watch.feed(f"{_LINE}\n{_LINE}\n")
    assert watch.feed(f"{_LINE}\n")


def test_a_line_split_across_pieces_counts_once_it_ends() -> None:
    watch = RepeatWatch("who sings?")
    assert not watch.feed(f"{_LINE}\n{_LINE}\nActually, I'll try ")
    assert not watch.feed("`read_text_file` again.")
    assert watch.feed("\n")


def test_surrounding_spaces_and_blank_lines_do_not_separate_copies() -> None:
    watch = RepeatWatch("who sings?")
    assert watch.feed(f"{_LINE}\n\n  {_LINE}\n \n{_LINE}  \n")


def test_a_short_line_never_repeats() -> None:
    watch = RepeatWatch("who sings?")
    assert not watch.feed("Let me check.\n" * 5)


def test_a_line_without_a_letter_never_repeats() -> None:
    watch = RepeatWatch("who sings?")
    assert not watch.feed("| --- | --- | --- | --- |\n" * 5)


@pytest.mark.parametrize("size", [2, 4])
def test_a_block_of_up_to_four_lines_three_times_is_a_repeat(size: int) -> None:
    watch = RepeatWatch("who sings?")
    block = "".join(f"Wait, I'll try reading part {n}.\n" for n in range(size))
    assert not watch.feed(block * 2 + block[:-1])
    assert watch.feed("\n")


def test_a_block_of_five_lines_is_no_repeat() -> None:
    watch = RepeatWatch("who sings?")
    assert not watch.feed("".join(f"Wait, I'll try reading part {n}.\n" for n in range(5)) * 3)


def test_two_copies_of_a_block_are_no_repeat() -> None:
    watch = RepeatWatch("who sings?")
    months = "".join(f"{m}: choir practice on the first Tuesday\n" for m in ("May", "June", "July"))
    assert not watch.feed(months * 2)


def test_a_line_with_other_lines_between_its_copies_never_repeats() -> None:
    watch = RepeatWatch("who sings?")
    shared = "Bring your sheet music and a pencil."
    assert not watch.feed("".join(f"Month {n}\n{shared}\n" for n in range(12)))


def test_a_line_the_message_holds_may_come_back_any_number_of_times() -> None:
    watch = RepeatWatch(_NAMED)
    assert not watch.feed(f"{_ASKED}\n" * 10 + f"- {_ASKED[:-1]}\n" * 3)


def test_a_block_with_a_line_the_message_lacks_still_repeats() -> None:
    watch = RepeatWatch(_NAMED)
    assert watch.feed(f"{_ASKED}\n{_LINE}\n" * 3)


def test_a_block_whose_only_counted_line_is_asked_for_never_repeats() -> None:
    watch = RepeatWatch(_NAMED)
    assert not watch.feed(f"Again:\n{_ASKED}\n" * 4)


def test_a_line_matches_the_message_only_in_whole_words() -> None:
    watch = RepeatWatch(f"Write '{_ASKED[:-1]}s' on every line.")
    assert watch.feed(f"{_ASKED}\n" * 3)


@pytest.mark.parametrize(
    ("query", "copies"),
    [
        (_MADE_UP, 11),
        ("Write it 5 times.", 6),
        ("Give me TWENTY copies of it.", 21),
        ("Write it seventeen times.", 18),
        ("Say it forty times.", 41),
        ("Say it a hundred times.", 101),
        ("Write it three times, then 12 times.", 13),
        ("Write it two times.", 3),
        ("Write it 0 times.", 3),
        ("I asked many times; it took 40 tries.", 3),
    ],
)
def test_a_count_the_message_asks_for_lets_that_many_copies_through(
    query: str, copies: int
) -> None:
    watch = RepeatWatch(query)
    assert not watch.feed(f"{_LINE}\n" * (copies - 1))
    assert watch.feed(f"{_LINE}\n")


def test_a_count_applies_to_a_block_of_several_lines() -> None:
    watch = RepeatWatch("Write the two lines 5 times.")
    block = f"{_LINE}\nWait, I'll try reading part two.\n"
    assert not watch.feed(block * 5)
    assert watch.feed(block)


def test_a_count_too_large_for_a_reply_lets_every_copy_through() -> None:
    watch = RepeatWatch(f"Write it {10**30} times.")
    assert not watch.feed(f"{_LINE}\n" * 200)


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


async def _reply(backend: _Looping, store: InMemorySessionStore, query: str = "who sings?") -> str:
    engine = TurnEngine(store, backend, _Clock())
    events = [event async for event in engine.handle_turn("s", query, turn_id="t-1")]
    shown = "".join(event.text for event in events if isinstance(event, TextDelta))
    completed = events[-1]
    assert isinstance(completed, TurnCompleted)
    assert completed.full_text == shown
    return shown


async def test_a_reply_repeating_one_line_ends_there_with_the_note_it_stores() -> None:
    store = InMemorySessionStore()
    backend = _Looping(["The file did not open.\n", *([f"{_LINE}\n"] * 6), "never read"])
    shown = await _reply(backend, store)
    note = REPEATED_LINE_NOTE.lstrip("\n")
    assert shown == "The file did not open.\n" + f"{_LINE}\n" * 3 + "\n" + note
    assert (await store.history("s"))[-1].text == shown
    assert backend.sent == 4
    assert backend.closed


async def test_a_note_after_a_line_and_a_blank_one_adds_no_line_break() -> None:
    backend = _Looping([f"{_LINE}\n\n"] * 4)
    shown = await _reply(backend, InMemorySessionStore())
    assert shown == f"{_LINE}\n\n" * 3 + REPEATED_LINE_NOTE.lstrip("\n")


async def test_a_note_after_text_past_the_line_break_starts_a_paragraph() -> None:
    backend = _Looping([f"{_LINE}\n", f"{_LINE}\n", f"{_LINE}\nSo I", " will"])
    shown = await _reply(backend, InMemorySessionStore())
    assert shown == f"{_LINE}\n" * 3 + "So I" + REPEATED_LINE_NOTE


async def test_a_reply_whose_lines_differ_runs_to_its_end_with_no_note() -> None:
    store = InMemorySessionStore()
    lines = [f"Week {n}: the altos sing the second verse.\n" for n in range(1, 6)]
    backend = _Looping(lines)
    assert await _reply(backend, store) == "".join(lines)
    assert backend.sent == 5


async def test_a_reply_repeating_the_line_the_person_asked_for_runs_to_its_end() -> None:
    lines = [f"{_ASKED}\n"] * 10
    backend = _Looping(lines)
    assert await _reply(backend, InMemorySessionStore(), _ASK) == "".join(lines)
    assert backend.sent == 10


async def test_a_line_the_model_made_up_and_was_asked_to_repeat_runs_to_its_end() -> None:
    lines = [f"{_LINE}\n"] * 10
    backend = _Looping(lines)
    assert await _reply(backend, InMemorySessionStore(), _MADE_UP) == "".join(lines)
    assert backend.sent == 10
