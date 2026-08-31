import os
from datetime import UTC, datetime

import httpx
import pytest

from cortex_core import (
    AttemptBounds,
    DecodeStop,
    GenerationBounds,
    InferenceEvent,
    Message,
    Role,
    SingleResidentModelManager,
    StopReason,
    SubagentTask,
    SystemClock,
    TextChunk,
)
from cortex_core.subagent_attempt import PlacedAttempt
from cortex_inference import LlamaCppBackend

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_ENDPOINT = os.environ.get("CORTEX_STOP_ENDPOINT", "http://127.0.0.1:8082")
_MODEL = os.environ.get("CORTEX_STOP_MODEL", "subagent")
# Small enough that the cap fires in seconds on a CPU tier decoding under 2 tokens a second, and
# large enough that the reply is visibly a cut sentence rather than an empty string.
_CAP = int(os.environ.get("CORTEX_STOP_MAX_TOKENS", "8"))
_ESSAY = "Write a long essay about the sea."
_ONE_WORD = "Reply with exactly one word: PONG."
_TIMEOUT_S = 600.0


def _messages(text: str) -> list[Message]:
    return [Message(role=Role.USER, text=text, at=datetime.now(UTC), turn_id="t-live")]


def _stops(events: list[InferenceEvent]) -> list[DecodeStop]:
    return [event for event in events if isinstance(event, DecodeStop)]


def _text(events: list[InferenceEvent]) -> str:
    return "".join(event.text for event in events if isinstance(event, TextChunk))


async def test_a_real_server_says_when_it_cut_a_completion_and_when_it_did_not() -> None:
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        capped = [
            event
            async for event in backend.stream(
                _MODEL, _messages(_ESSAY), bounds=GenerationBounds(max_tokens=_CAP)
            )
        ]
        finished = [event async for event in backend.stream(_MODEL, _messages(_ONE_WORD))]

    print(f"\ncapped at {_CAP}: {_stops(capped)}, text {_text(capped)!r}")  # noqa: T201
    print(f"uncapped:        {_stops(finished)}, text {_text(finished)!r}")  # noqa: T201
    assert _stops(capped) == [DecodeStop(StopReason.CAPPED)]
    assert _stops(finished) == [DecodeStop(StopReason.FINISHED)]
    assert _text(capped), "a cap this small should still have produced the words it managed"


async def test_the_core_reads_a_capped_delegated_reply_as_unanswered() -> None:
    task = SubagentTask(id="t-live", instruction=_ESSAY, context="", at=datetime.now(UTC))
    attempt = PlacedAttempt(
        SystemClock(),
        None,
        constrain_output=False,
        bounds=AttemptBounds(max_tokens=_CAP, timeout_s=_TIMEOUT_S),
    )
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        outcome = await attempt.run(task, _MODEL, backend, budget=None, progress=None)

    print(f"\noutcome: ok={outcome.ok} text={outcome.text!r}\ndetail: {outcome.detail}")  # noqa: T201
    assert outcome.ok is False
    assert "stopped at a token limit" in outcome.detail
    assert f"{_CAP} decoded tokens per completion" in outcome.detail
