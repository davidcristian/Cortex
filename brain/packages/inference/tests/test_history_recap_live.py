"""What does recapping a dropped prefix cost, and does it keep what a follow-up needs?

Integration-marked: excluded from CI and the coverage gate by the workspace addopts
(`-m "not integration"`). Needs the gpu stack for the resident cortex:

    cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 \
      uv run pytest -m integration --no-cov packages/inference/tests/test_history_recap_live.py -s

The corpus is a long conversation whose opening turns carry facts a later question depends on,
and whose middle is filler, so a character budget pushes those facts out of the window. Then the
same question is asked twice: once with the char-budget window that ships, and once with the
summarizing window over it. What is measured is the prompt each one hands the model (in
characters, the same unit the budget is denominated in), the wall time to the reply's first
token, and whether the answer actually contains the fact from the dropped opening.
"""

import os
import time
from datetime import UTC, datetime

import httpx
import pytest

from cortex_core import (
    CharBudgetHistoryWindow,
    InMemorySessionStore,
    Message,
    Role,
    SingleResidentModelManager,
    TextChunk,
)
from cortex_core.summarizing import SummarizingHistoryWindow
from cortex_inference import LlamaCppBackend

_MODEL = os.environ.get("CORTEX_MODEL_CORTEX", "cortex")
_ENDPOINT = os.environ.get("CORTEX_INFERENCE_ENDPOINT", "http://127.0.0.1:8080")
_AT = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
_SESSION = "recap-live"

# The budget is small on purpose: it is the ratio of window to conversation that matters, and a
# short corpus keeps the run to one generation per arm rather than a long transcript's worth.
_BUDGET = 350

# The facts the opening turns carry. The question at the end depends on the first of them, and
# nothing after it repeats the number, so a window that merely truncates cannot answer.
_OPENING = [
    ("my booking reference is QH7-4412 and the flight lands at 06:20", "Noted, QH7-4412 at 06:20."),
    ("the hotel is the Marlow on Gilbert Street, checking in late", "The Marlow, late check-in."),
    ("put the whole trip on the personal card, not the company one", "Personal card it is."),
]

# Filler that pushes the opening out of the window without repeating anything from it.
_FILLER = [
    ("what is the weather usually like there in spring?", "Mild, with rain most weeks."),
    ("is the tap water fine to drink?", "Yes, it is treated and safe everywhere in the city."),
    ("do I need an adapter for the sockets?", "Yes, a type G adapter."),
    ("how far is the centre from the airport?", "About forty minutes by train."),
    ("are the museums open on Mondays?", "Most close on Mondays; the maritime one does not."),
    ("should I book restaurants ahead?", "For the weekend, yes."),
    ("is the transit card worth it?", "If you make more than three trips a day."),
    ("what plug voltage do they run?", "Two hundred and thirty volts."),
]

_QUESTION = "remind me of my booking reference"
_FACT = "QH7-4412"


def _history() -> list[Message]:
    """The opening exchanges, the filler, then the question, as one session's stored history."""
    messages: list[Message] = []
    for index, (user, assistant) in enumerate([*_OPENING, *_FILLER]):
        turn = f"t{index}"
        messages.append(Message(role=Role.USER, text=user, at=_AT, turn_id=turn))
        messages.append(Message(role=Role.ASSISTANT, text=assistant, at=_AT, turn_id=turn))
    messages.append(Message(role=Role.USER, text=_QUESTION, at=_AT, turn_id="ask"))
    return messages


class _FixedClock:
    def now(self) -> datetime:
        return _AT


async def _answer(backend: LlamaCppBackend, prompt: list[Message]) -> tuple[str, float]:
    """Stream one reply, returning its text and the seconds to its FIRST token."""
    started = time.monotonic()
    first: float | None = None
    parts: list[str] = []
    stream = backend.stream(_MODEL, prompt)
    async for event in stream:
        if isinstance(event, TextChunk):
            if first is None:
                first = time.monotonic() - started
            parts.append(event.text)
    return "".join(parts), (first if first is not None else time.monotonic() - started)


@pytest.mark.integration
async def test_the_recap_is_measured_against_the_window_that_ships() -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        history = _history()
        plain = CharBudgetHistoryWindow(_BUDGET)
        store = InMemorySessionStore()
        summarizing = SummarizingHistoryWindow(plain, store, backend, _MODEL, _FixedClock())

        shipped = list(await plain.select(history, session_id=_SESSION))
        # The first selection pays for the recap; the second is the cached read every later turn
        # of the same boundary gets, which is what the feature actually costs in steady state.
        cold_started = time.monotonic()
        recapped = list(await summarizing.select(history, session_id=_SESSION))
        recap_cost = time.monotonic() - cold_started
        warm_started = time.monotonic()
        await summarizing.select(history, session_id=_SESSION)
        cached_cost = time.monotonic() - warm_started

        shipped_answer, shipped_ttft = await _answer(backend, shipped)
        recapped_answer, recapped_ttft = await _answer(backend, recapped)

        shipped_chars = sum(len(m.text) for m in shipped)
        recapped_chars = sum(len(m.text) for m in recapped)
        stored = await store.recap(_SESSION)
        print(  # noqa: T201 -- the measurement IS this test's output
            f"\nhistory {len(history)} messages, {sum(len(m.text) for m in history)} chars"
            f"\nshipped window: {len(shipped)} messages, {shipped_chars} chars"
            f"\nrecapped window: {len(recapped)} messages, {recapped_chars} chars"
            f"\nrecap pass: {recap_cost:.1f}s cold, {cached_cost:.3f}s cached"
            f"\nreply first token: shipped {shipped_ttft:.1f}s, recap {recapped_ttft:.1f}s"
            f"\nrecap: {stored.text if stored else '(none)'}"
            f"\nasked: {_QUESTION}"
            f"\nshipped answer: {shipped_answer.strip()}"
            f"\nrecapped answer: {recapped_answer.strip()}"
            f"\nfact {_FACT} kept: shipped {_FACT in shipped_answer},"
            f" recapped {_FACT in recapped_answer}"
        )
        # The numbers are the point; the assertions pin only that the arms really differ, so a
        # run where the recap silently did not happen cannot be read as a measurement of it.
        assert stored is not None
        assert _FACT not in "".join(m.text for m in shipped)  # the fact really did drop out
        assert len(recapped) == len(shipped) + 1  # and the recap really did ride along
