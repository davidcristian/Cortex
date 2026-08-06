"""Behavior of the summarizing history window (ADR-0038 decision 9).

Three properties carry the design and each has its own group here: the window can only ADD to
what the char-budget window kept (so no failure of the summarizer costs the user a word they
wrote), the recap is CACHED by the boundary it covers and folded forward rather than recomputed,
and the model pass LETS GO of the GPU lease before the reply asks for it.

That last group is the one the backlog named as the hazard for weeks, so it is tested against the
real ``SingleResidentModelManager`` and its real non-reentrant lock rather than a stand-in, and
it is tested in both directions: the disciplined window's selection is followed by a second
acquire that must succeed, and a deliberately undisciplined summarizer is followed by the same
acquire, which must deadlock. Without that second test the first proves nothing, because a
harness whose lock is never really held is green either way.
"""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from cortex_core import (
    InferenceError,
    InMemorySessionStore,
    Message,
    Role,
    SessionStoreError,
    SingleResidentModelManager,
    TextChunk,
    ToolSpec,
)
from cortex_core.inference import InferenceEvent, JsonSchema
from cortex_core.sessions import RECAP_MAX, HistoryRecap
from cortex_core.summarizing import SummarizingHistoryWindow, build_recap_messages, clean_recap
from cortex_core.windowing import CharBudgetHistoryWindow

_AT = datetime(2026, 8, 6, 12, 0, 0, tzinfo=UTC)
_SESSION = "s-1"


class _FixedClock:
    """A Clock pinned to one instant so the recap preface's timestamp is assertable."""

    def __init__(self, at: datetime) -> None:
        self._at = at

    def now(self) -> datetime:
        return self._at


def _turn(turn_id: str, user: str, assistant: str) -> list[Message]:
    return [
        Message(role=Role.USER, text=user, at=_AT, turn_id=turn_id),
        Message(role=Role.ASSISTANT, text=assistant, at=_AT, turn_id=turn_id),
    ]


def _history(turns: int, *, size: int = 20) -> list[Message]:
    """``turns`` exchanges of a fixed size, so a budget picks a predictable number of them."""
    return [
        message
        for index in range(turns)
        for message in _turn(
            f"t{index}", f"q{index}".ljust(size, "."), f"a{index}".ljust(size, ".")
        )
    ]


class _ScriptedBackend:
    """An InferenceBackend that replies with canned text and records what it was asked."""

    def __init__(self, replies: Sequence[str], *, fail: bool = False) -> None:
        self._replies = list(replies)
        self._fail = fail
        self.prompts: list[str] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema
        self.prompts.append(messages[-1].text)
        if self._fail:
            msg = "llama-server is not answering"
            raise InferenceError(msg)
        yield TextChunk(self._replies.pop(0) if self._replies else "")


class _BrokenStore(InMemorySessionStore):
    """A session store whose recap read fails, standing in for Redis being unreachable."""

    async def recap(self, session_id: str) -> HistoryRecap | None:
        msg = f"recap read for session {session_id!r} failed"
        raise SessionStoreError(msg)


def _window(
    backend: _ScriptedBackend, store: InMemorySessionStore, *, budget: int = 60
) -> SummarizingHistoryWindow:
    return SummarizingHistoryWindow(
        CharBudgetHistoryWindow(budget), store, backend, "cortex", _FixedClock(_AT)
    )


# --- it can only add -------------------------------------------------------------------------


async def test_a_history_that_fits_is_returned_untouched_and_costs_no_model_call() -> None:
    store, backend = InMemorySessionStore(), _ScriptedBackend(["never asked for"])
    history = _history(1)
    assert list(await _window(backend, store).select(history, session_id=_SESSION)) == history
    assert backend.prompts == []  # nothing dropped, so nothing to recap
    assert await store.recap(_SESSION) is None


async def test_the_recap_is_prepended_and_the_kept_tail_is_byte_for_byte_the_plain_window() -> None:
    store, backend = InMemorySessionStore(), _ScriptedBackend(["they talked about q0 and q1"])
    history = _history(4)
    plain = await CharBudgetHistoryWindow(60).select(history, session_id=_SESSION)

    selected = await _window(backend, store).select(history, session_id=_SESSION)

    assert list(selected[1:]) == list(plain)  # the tail is untouched, message for message
    preface = selected[0]
    assert preface.role is Role.SYSTEM
    assert "they talked about q0 and q1" in preface.text
    # Stamped with the last turn it accounts for, not the turn now being answered.
    assert preface.turn_id == history[len(history) - len(plain) - 1].turn_id


async def test_a_model_failure_degrades_to_the_plain_window_rather_than_failing_the_turn() -> None:
    store, backend = InMemorySessionStore(), _ScriptedBackend([], fail=True)
    history = _history(4)
    plain = await CharBudgetHistoryWindow(60).select(history, session_id=_SESSION)

    selected = await _window(backend, store).select(history, session_id=_SESSION)

    assert list(selected) == list(plain)  # exactly what ships today, no prefix, no exception
    assert await store.recap(_SESSION) is None  # and nothing was cached from the failure


async def test_an_unreachable_store_degrades_to_the_plain_window() -> None:
    store, backend = _BrokenStore(), _ScriptedBackend(["unused"])
    history = _history(4)
    plain = await CharBudgetHistoryWindow(60).select(history, session_id=_SESSION)
    assert list(await _window(backend, store).select(history, session_id=_SESSION)) == list(plain)


async def test_a_model_that_says_nothing_usable_is_not_stored_and_not_prepended() -> None:
    """A reasoning cortex can spend its whole budget thinking and emit no reply text.

    That is not an error, so it must not raise; it is also not a recap, so it must not be cached
    under a boundary it does not describe, which would poison every later fold.
    """
    store, backend = InMemorySessionStore(), _ScriptedBackend(["   \n  "])
    history = _history(4)
    plain = await CharBudgetHistoryWindow(60).select(history, session_id=_SESSION)
    assert list(await _window(backend, store).select(history, session_id=_SESSION)) == list(plain)
    assert await store.recap(_SESSION) is None


# --- it caches, keyed by the boundary --------------------------------------------------------


async def test_a_recap_at_the_same_boundary_is_reused_without_a_second_model_call() -> None:
    store, backend = InMemorySessionStore(), _ScriptedBackend(["the opening exchanges"])
    window, history = _window(backend, store), _history(4)

    first = await window.select(history, session_id=_SESSION)
    second = await window.select(history, session_id=_SESSION)

    assert len(backend.prompts) == 1  # the boundary did not move, so the cache answered
    assert list(first) == list(second)
    stored = await store.recap(_SESSION)
    assert stored is not None
    assert stored.covers == len(history) - (len(first) - 1)


async def test_a_moved_boundary_folds_the_previous_recap_forward_instead_of_rereading() -> None:
    store = InMemorySessionStore()
    backend = _ScriptedBackend(["the first stretch", "the first stretch, then more"])
    window = _window(backend, store)

    await window.select(_history(4), session_id=_SESSION)
    grown = _history(6)
    selected = await window.select(grown, session_id=_SESSION)

    assert len(backend.prompts) == 2
    fold = backend.prompts[1]
    assert "the first stretch" in fold  # the previous recap went in as the account so far
    assert "q0" not in fold  # and the turns it already covered did NOT go in again
    assert "q3" in fold  # only what has dropped since
    assert "the first stretch, then more" in selected[0].text


async def test_a_recap_covering_more_than_the_boundary_is_rebuilt_from_scratch() -> None:
    """A widened character budget pulls messages back into the window, so the stored recap
    would duplicate them. It is dropped rather than folded, and the fresh pass sees the whole
    prefix, which self-heals the session on the spot.
    """
    store, backend = InMemorySessionStore(), _ScriptedBackend(["a fresh account"])
    await store.set_recap(_SESSION, HistoryRecap(text="covers far too much", covers=99))

    selected = await _window(backend, store).select(_history(4), session_id=_SESSION)

    assert "covers far too much" not in backend.prompts[0]  # not folded in
    assert "q0" in backend.prompts[0]  # the whole dropped prefix was read instead
    assert "a fresh account" in selected[0].text
    stored = await store.recap(_SESSION)
    assert stored is not None
    assert stored.covers == 6


async def test_a_recap_survives_a_model_swap_because_it_is_text_in_the_store() -> None:
    """The hard rule for this feature: nothing about the recap lives in a model process.

    The first window writes the recap and is then thrown away together with its backend, which
    is what a swap does to the model that wrote it. A second window over the SAME store and a
    backend that would answer differently reads the original text back and never calls the model,
    so the recap crossed the swap intact.
    """
    store = InMemorySessionStore()
    writer = _ScriptedBackend(["what the departed model wrote"])
    history = _history(4)
    await _window(writer, store).select(history, session_id=_SESSION)

    successor = _ScriptedBackend(["a different model's words"])
    selected = await _window(successor, store).select(history, session_id=_SESSION)

    assert "what the departed model wrote" in selected[0].text
    assert successor.prompts == []  # rehydrated from the store, not regenerated


async def test_deleting_the_session_takes_its_recap_with_it() -> None:
    store, backend = InMemorySessionStore(), _ScriptedBackend(["about the secret", "written again"])
    window, history = _window(backend, store), _history(4)
    await window.select(history, session_id=_SESSION)

    await store.delete(_SESSION)

    assert await store.recap(_SESSION) is None
    await window.select(history, session_id=_SESSION)  # and the next turn starts over
    assert len(backend.prompts) == 2


# --- it lets go of the GPU lease -------------------------------------------------------------


class _LeasedBackend:
    """The shape of the real inference adapter: the lease is held for the generator's lifetime.

    ``LlamaCppBackend.stream`` opens ``async with manager.acquire(model)`` around its whole SSE
    loop, so the non-reentrant lock is held until the generator is exhausted or closed. This
    reproduces exactly that, over the real ``SingleResidentModelManager``.
    """

    def __init__(self, manager: SingleResidentModelManager, reply: str) -> None:
        self._manager = manager
        self._reply = reply
        self.released = False

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del messages, tools, schema
        try:
            async with self._manager.acquire(model):
                yield TextChunk(self._reply)
        finally:
            self.released = True


async def test_selection_leaves_the_acquire_block_before_it_returns() -> None:
    """The lease is released at a point in the code, not at the collector's convenience.

    ``released`` is checked with no ``await`` between it and ``select``'s return, which is what
    makes this able to fail: a summarizer that read its chunk and walked away leaves the
    generator suspended inside the adapter's acquire block right then, and only a later
    asynchronous-generator finalization would tidy it up. Draining and closing is the whole
    difference, and it is the difference this assertion sees.
    """
    manager = SingleResidentModelManager("cortex", "http://127.0.0.1:8080")
    backend = _LeasedBackend(manager, "the recap")
    window = SummarizingHistoryWindow(
        CharBudgetHistoryWindow(60), InMemorySessionStore(), backend, "cortex", _FixedClock(_AT)
    )

    selected = await window.select(_history(4), session_id=_SESSION)

    assert backend.released  # no await in between: the block was left, not finalized later
    assert "the recap" in selected[0].text


async def test_the_reply_can_then_take_the_lease() -> None:
    """Selection completes, then the reply acquires: a sequence, never a nested acquire.

    This is the turn's real order (``assemble_inference_messages`` is awaited to completion
    several statements before ``handle_turn`` first iterates the reply's generator), run against
    the real lock rather than a stand-in.
    """
    manager = SingleResidentModelManager("cortex", "http://127.0.0.1:8080")
    backend = _LeasedBackend(manager, "the recap")
    window = SummarizingHistoryWindow(
        CharBudgetHistoryWindow(60), InMemorySessionStore(), backend, "cortex", _FixedClock(_AT)
    )

    selected = await window.select(_history(4), session_id=_SESSION)

    async with asyncio.timeout(2):
        reply = [event async for event in backend.stream("cortex", selected)]
    assert reply == [TextChunk("the recap")]


async def test_a_summarizer_that_abandoned_its_stream_would_strand_the_lease() -> None:
    """The falsification twin: prove the harness above can actually deadlock.

    A selection-time call that reads one event and walks away leaves the generator suspended
    inside the adapter's acquire block, so the reply's acquire waits on a lease nobody is using.
    ``drain_text`` is what the summarizing window uses instead, and this test is what makes its
    green mean something: without it, a lock that was never really held would pass either way.
    """
    manager = SingleResidentModelManager("cortex", "http://127.0.0.1:8080")
    backend = _LeasedBackend(manager, "half a recap")

    # The port promises only an AsyncIterator; this backend's is a generator, which is what
    # holds a suspended `finally` and therefore the lease. The narrowing is also the assertion.
    abandoned = cast("AsyncGenerator[InferenceEvent, None]", backend.stream("cortex", []))
    assert await anext(abandoned) == TextChunk("half a recap")  # suspended, still holding

    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.2):
            await anext(backend.stream("cortex", []))
    await abandoned.aclose()  # release it so the event loop closes cleanly


# --- the pure pieces -------------------------------------------------------------------------


def test_a_first_recap_prompt_carries_no_previous_account() -> None:
    prompt = build_recap_messages(None, _turn("t0", "hello", "hi"), at=_AT, turn_id="t0")
    assert len(prompt) == 1
    assert "The account so far" not in prompt[0].text
    assert "user: hello" in prompt[0].text
    assert "assistant: hi" in prompt[0].text


def test_a_recap_reply_is_collapsed_and_bounded() -> None:
    assert clean_recap("  they  agreed\n\nto ship  ") == "they agreed to ship"
    assert clean_recap("") == ""
    assert len(clean_recap("x " * RECAP_MAX)) == RECAP_MAX


def test_a_recap_value_refuses_to_be_blank_or_cover_nothing() -> None:
    with pytest.raises(ValueError, match="no text"):
        HistoryRecap(text="  ", covers=3)
    with pytest.raises(ValueError, match="at least one message"):
        HistoryRecap(text="fine", covers=0)


async def test_the_preface_is_timestamped_by_the_clock_not_by_the_dropped_turns() -> None:
    store, backend = InMemorySessionStore(), _ScriptedBackend(["an account"])
    later = _AT + timedelta(hours=3)
    window = SummarizingHistoryWindow(
        CharBudgetHistoryWindow(60), store, backend, "cortex", _FixedClock(later)
    )
    selected = await window.select(_history(4), session_id=_SESSION)
    assert selected[0].at == later
