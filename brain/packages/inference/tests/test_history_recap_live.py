import os
import time
from collections.abc import Sequence
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
from cortex_core.drain import drain_text
from cortex_core.inference import GenerationBounds
from cortex_core.recap_prompt import RECAP_BOUNDS, build_recap_messages, clean_recap
from cortex_core.summarizing import SummarizingHistoryWindow
from cortex_core.untrusted import wrap_untrusted
from cortex_inference import LlamaCppBackend

_MODEL = os.environ.get("CORTEX_MODEL_CORTEX", "cortex")
_ENDPOINT = os.environ.get("CORTEX_INFERENCE_ENDPOINT", "http://127.0.0.1:8080")
_AT = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
_SESSION = "recap-live"

# Small on purpose: what matters is the ratio of window to conversation, and a short corpus
# keeps the run to one generation per case rather than a transcript's worth.
_BUDGET = 350

_OPENING = [
    ("my booking reference is QH7-4412 and the flight lands at 06:20", "Noted, QH7-4412 at 06:20."),
    ("the hotel is the Marlow on Gilbert Street, checking in late", "The Marlow, late check-in."),
    ("put the whole trip on the personal card, not the company one", "Personal card it is."),
]

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

_MORE_FILLER = [
    ("do the buses run through the night?", "On the two main lines only."),
    ("is tipping expected in cafes?", "Rounding up is enough."),
    ("what is the currency there?", "The local krona; cards work everywhere."),
    ("is the old town walkable?", "Entirely, and it is mostly flat."),
    ("do I need a reservation for the ferry?", "Not in spring."),
    ("how early should I get to the airport?", "Two hours is plenty."),
]

_QUESTION = "remind me of my booking reference"
_FACT = "QH7-4412"

# Taken from the wrap rather than copied from it, so a leak check here follows what
# ``wrap_untrusted`` really renders.
_FENCE_TAG = wrap_untrusted("", nonce="0").split(" ", 1)[0].lstrip("<")


def _exchanges(pairs: Sequence[tuple[str, str]]) -> list[Message]:
    """Render ``pairs`` as stored history: one user message and one assistant reply each."""
    messages: list[Message] = []
    for index, (user, assistant) in enumerate(pairs):
        turn = f"t{index}"
        messages.append(Message(role=Role.USER, text=user, at=_AT, turn_id=turn))
        messages.append(Message(role=Role.ASSISTANT, text=assistant, at=_AT, turn_id=turn))
    return messages


def _asking(pairs: Sequence[tuple[str, str]]) -> list[Message]:
    """Return those exchanges with the follow-up appended, as a turn hands them to the window."""
    return [*_exchanges(pairs), Message(role=Role.USER, text=_QUESTION, at=_AT, turn_id="ask")]


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
        history = _asking([*_OPENING, *_FILLER])
        plain = CharBudgetHistoryWindow(_BUDGET)
        store = InMemorySessionStore()
        summarizing = SummarizingHistoryWindow(plain, store, backend, _MODEL, _FixedClock())

        shipped = list(await plain.select(history, session_id=_SESSION))
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
            f"\nrecap text {len(stored.text) if stored else 0} chars,"
            f" fenced {len(recapped[0].text)} chars"
            f"\nasked: {_QUESTION}"
            f"\nshipped answer: {shipped_answer.strip()}"
            f"\nrecapped answer: {recapped_answer.strip()}"
            f"\nfact {_FACT} kept: shipped {_FACT in shipped_answer},"
            f" recapped {_FACT in recapped_answer}"
        )
        assert stored is not None
        assert _FACT not in "".join(m.text for m in shipped)
        assert len(recapped) == len(shipped) + 1
        assert _FACT not in shipped_answer
        assert _FACT in recapped_answer
        assert _FENCE_TAG not in recapped_answer


# How many of the staged runs below are played out. Retention across repeated folds varies
# between runs, so one sample would be an anecdote in either direction and this reports a rate.
_ROUNDS = 3

_GROWTH = [_FILLER[2:4], _FILLER[4:6], _FILLER[6:8], _MORE_FILLER[:2], _MORE_FILLER[2:4]]


@pytest.mark.integration
async def test_a_fact_survives_being_folded_forward_several_times() -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        plain = CharBudgetHistoryWindow(_BUDGET)
        in_recap = 0
        in_reply = 0
        for round_index in range(_ROUNDS):
            store = InMemorySessionStore()
            summarizing = SummarizingHistoryWindow(
                plain, store, backend, _MODEL, _FixedClock(), min_dropped_chars=0
            )
            session = f"{_SESSION}-folded-{round_index}"

            grown = [*_OPENING, *_FILLER[:2]]
            folds: list[tuple[int, float]] = []
            for pair in _GROWTH:
                grown = [*grown, *pair]
                started = time.monotonic()
                await summarizing.select(_asking(grown), session_id=session)
                elapsed = time.monotonic() - started
                covers = await store.recap(session)
                folds.append(((covers.covers if covers else 0), elapsed))

            history = _asking(grown)
            shipped = list(await plain.select(history, session_id=session))
            recapped = list(await summarizing.select(history, session_id=session))
            shipped_answer, _ = await _answer(backend, shipped)
            recapped_answer, _ = await _answer(backend, recapped)
            stored = await store.recap(session)
            kept = stored is not None and _FACT in stored.text
            quoted = _FACT in recapped_answer
            in_recap += int(kept)
            in_reply += int(quoted)
            print(  # noqa: T201 -- the measurement IS this test's output
                f"\nround {round_index}: history {len(history)} messages,"
                f" {sum(len(m.text) for m in history)} chars"
                f"\nfolds (boundary, seconds): {[(c, round(s, 1)) for c, s in folds]}"
                f"\nshipped window: {len(shipped)} messages,"
                f" {sum(len(m.text) for m in shipped)} chars"
                f"\nrecapped window: {len(recapped)} messages,"
                f" {sum(len(m.text) for m in recapped)} chars"
                f"\nrecap after {len(folds)} folds: {stored.text if stored else '(none)'}"
                f"\nshipped answer: {shipped_answer.strip()}"
                f"\nrecapped answer: {recapped_answer.strip()}"
                f"\nfact {_FACT}: in the recap {kept}, in the reply {quoted}"
            )
            assert stored is not None
            assert len({covers for covers, _ in folds}) == len(folds)
            assert _FACT not in shipped_answer
            assert _FENCE_TAG not in recapped_answer
        print(  # noqa: T201 -- the measurement IS this test's output
            f"\nafter {len(_GROWTH)} folds, over {_ROUNDS} rounds:"
            f" the fact survived the fold {in_recap}/{_ROUNDS},"
            f" and reached the reply {in_reply}/{_ROUNDS}"
        )


_PRICING_RUNS = 3


def _fold_prompt() -> list[Message]:
    """Build the prompt one fold sends: a session's first account of its dropped opening."""
    dropped = _exchanges([*_OPENING, *_FILLER[:2]])
    return build_recap_messages(None, dropped, at=_AT, turn_id="t4")


@pytest.mark.integration
async def test_the_fold_costs_less_once_it_stops_paying_for_thinking_nobody_reads() -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        prompt = _fold_prompt()
        timings: dict[str, list[float]] = {"unbounded": [], "bounded": []}
        accounts: dict[str, list[str]] = {"unbounded": [], "bounded": []}
        for _ in range(_PRICING_RUNS):
            for label, bounds in (("unbounded", None), ("bounded", RECAP_BOUNDS)):
                started = time.monotonic()
                raw = await drain_text(backend, _MODEL, prompt, bounds=bounds)
                timings[label].append(time.monotonic() - started)
                accounts[label].append(clean_recap(raw))
        print(  # noqa: T201 -- the measurement IS this test's output
            f"\nfold prompt: {sum(len(m.text) for m in prompt)} chars"
            f"\nunbounded (the request that shipped): "
            f"{[round(s, 1) for s in timings['unbounded']]} s,"
            f" accounts {[len(a) for a in accounts['unbounded']]} chars"
            f"\nbounded ({RECAP_BOUNDS}): {[round(s, 1) for s in timings['bounded']]} s,"
            f" accounts {[len(a) for a in accounts['bounded']]} chars"
            f"\nbounded account: {accounts['bounded'][-1]}"
        )
        assert all(accounts["bounded"])
        assert all(_FACT in account for account in accounts["bounded"])
        assert sum(timings["bounded"]) < sum(timings["unbounded"])


@pytest.mark.integration
async def test_a_small_cap_against_a_thinking_model_is_the_trap_the_pairing_avoids() -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        prompt = _fold_prompt()
        thinking_and_capped = GenerationBounds(max_tokens=RECAP_BOUNDS.max_tokens, thinking=True)
        raw = await drain_text(backend, _MODEL, prompt, bounds=thinking_and_capped)
        print(  # noqa: T201 -- the measurement IS this test's output
            f"\nthinking on, capped at {thinking_and_capped.max_tokens}:"
            f" {len(raw)} chars of reply, usable: {bool(clean_recap(raw))}"
        )
        paired = await drain_text(backend, _MODEL, prompt, bounds=RECAP_BOUNDS)
        assert clean_recap(paired)


# The floor ``build_history_window`` computes rather than the raw default: it is clamped to the
# character budget, and this corpus runs on a deliberately tiny one.
_DEFAULT_FLOOR = 2_000
_SHIPPED_FLOOR = min(_DEFAULT_FLOOR, _BUDGET)


@pytest.mark.integration
async def test_the_shipped_fold_floor_pays_for_fewer_folds_over_the_same_conversation() -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        plain = CharBudgetHistoryWindow(_BUDGET)
        in_recap = 0
        for round_index in range(_ROUNDS):
            store = InMemorySessionStore()
            floored = SummarizingHistoryWindow(
                plain, store, backend, _MODEL, _FixedClock(), min_dropped_chars=_SHIPPED_FLOOR
            )
            session = f"{_SESSION}-floored-{round_index}"
            grown = [*_OPENING, *_FILLER[:2]]
            boundaries: list[int] = []
            elapsed = 0.0
            for pair in _GROWTH:
                grown = [*grown, *pair]
                started = time.monotonic()
                await floored.select(_asking(grown), session_id=session)
                elapsed += time.monotonic() - started
                covers = await store.recap(session)
                boundaries.append(covers.covers if covers else 0)
            stored = await store.recap(session)
            kept = stored is not None and _FACT in stored.text
            in_recap += int(kept)
            folds = len(set(boundaries) - {0})
            print(  # noqa: T201 -- the measurement IS this test's output
                f"\nround {round_index} at floor {_SHIPPED_FLOOR}:"
                f" {folds} folds over {len(_GROWTH)} boundary moves, {elapsed:.1f}s total"
                f"\nboundaries: {boundaries}"
                f"\nrecap: {stored.text if stored else '(none)'}"
                f"\nfact {_FACT} in the recap: {kept}"
            )
        print(  # noqa: T201 -- the measurement IS this test's output
            f"\nat floor {_SHIPPED_FLOOR}, over {_ROUNDS} rounds:"
            f" the fact survived {in_recap}/{_ROUNDS}"
        )
