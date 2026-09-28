import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import httpx
import pytest

from cortex_core import (
    BRAIN_OVERFLOW_NOTE,
    BrainPhase,
    ContextOverflowError,
    HandoffRecord,
    HandoffState,
    InMemorySessionStore,
    Message,
    Role,
    SingleResidentModelManager,
    SystemClock,
    TextDelta,
    TurnCapabilities,
    TurnEvent,
)
from cortex_inference import LlamaCppBackend

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_ENDPOINT = os.environ.get("CORTEX_OVERFLOW_ENDPOINT", "http://127.0.0.1:8081")
_MODEL = os.environ.get("CORTEX_OVERFLOW_MODEL", "brain")
_SESSION = "s-overflow"
_TURN = "t-overflow"
_TIMEOUT_S = 300.0


async def _over_length_text(client: httpx.AsyncClient) -> str:
    """A text of about twice the served context, one token a word on the tokenizers drawn."""
    props = (await client.get(f"{_ENDPOINT}/props")).json()
    n_ctx = int(props["default_generation_settings"]["n_ctx"])
    return "word " * (2 * n_ctx)


async def _collect(events: AsyncGenerator[TurnEvent, None], into: list[str]) -> None:
    """Collect a phase's text into ``into``, letting whatever it raises propagate."""
    async for event in events:
        if isinstance(event, TextDelta):
            into.append(event.text)  # noqa: PERF401 - a live stream, read one event at a time


async def test_a_real_server_refuses_an_over_length_prompt_as_an_overflow() -> None:
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        text = await _over_length_text(client)
        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        message = Message(role=Role.USER, text=text, at=datetime.now(UTC), turn_id=_TURN)
        with pytest.raises(ContextOverflowError) as excinfo:
            _ = [event async for event in backend.stream(_MODEL, [message])]
    print(f"\n{excinfo.value}")  # noqa: T201
    assert "exceeds the available context size" in str(excinfo.value)


async def test_an_over_length_handoff_tells_the_user_it_did_not_fit() -> None:
    clock = SystemClock()
    sessions = InMemorySessionStore()
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        text = await _over_length_text(client)
        await sessions.append(
            _SESSION, Message(role=Role.USER, text=text, at=clock.now(), turn_id=_TURN)
        )
        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        phase = BrainPhase(sessions, backend, clock, _MODEL, TurnCapabilities())
        record = HandoffRecord(
            handoff_id=_TURN,
            session_id=_SESSION,
            requested_at=clock.now(),
            state=HandoffState.BRAIN_ACTIVE,
            brief="answer the long message",
            nonce="f00ddeadbeef0002",
            tainted=False,
            opaque=False,
            sources=(),
            untrusted_urls=frozenset(),
            budget_remaining=4,
            budget_closed=False,
            rounds_used=0,
            loop_tail=(),
        )
        told: list[str] = []
        with pytest.raises(ContextOverflowError):
            await _collect(phase.run(record), told)
    persisted = await sessions.history(_SESSION)
    print(f"\ntold: {''.join(told)!r}")  # noqa: T201
    assert "".join(told) == BRAIN_OVERFLOW_NOTE
    assert persisted[-1].text == BRAIN_OVERFLOW_NOTE
