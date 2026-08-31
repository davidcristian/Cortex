"""Integration: the stop reason off a real llama-server, and the capped verdict the core reads.

The fakes prove the parsing and the policy; this proves that a real server reports the reason at
all, that a request capped at `max_tokens` really comes back saying so, and that the shipped
`PlacedAttempt` turns that into an `ok=False` outcome instead of an answer. That last step is the
whole claim of the arm, because before it a delegated reply the server had cut was read as a short
one.

Integration-marked, so CI and the coverage gate never see it (AGENTS.md gate 3). It needs the CPU
subagent tier, which needs no GPU:

    CORTEX_MODELS_DIR=/srv/models docker compose --project-directory . \\
      -f docker/docker-compose.yml -f docker/docker-compose.subagents.yml up -d llama-subagent
    cd brain && CORTEX_STOP_ENDPOINT=http://127.0.0.1:8082 \\
      uv run pytest -m integration --no-cov -s \\
      packages/inference/tests/test_finish_reason_live.py

`CORTEX_STOP_ENDPOINT` is where that server answers. Under WSL with mirrored networking the
loopback publish above can refuse from the host while the container is healthy; the container's own
address on the compose network works, so point the variable at that instead of retuning docker.

Measured 2026-08-16 by the agent on the shipped CPU tier (gemma-4-E4B QAT q4_0, `-ngl 0`,
llama.cpp build `b9879-72874f559`), by this suite as written:

| arm | request | what came back |
| --- | --- | --- |
| capped | `max_tokens: 8`, an essay prompt | `finish_reason: "length"`, cut mid-sentence |
| finished | no cap, "reply with one word" | `finish_reason: "stop"` |
| the core | the capped arm through `PlacedAttempt` | `ok=False`, the refusal naming the cap |

The first two rows are the port's two answers derived from a real server rather than a transcript;
the third is the consumer that makes them worth carrying.
"""

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
# Small enough that the cap fires in seconds on a CPU tier decoding under 2 tok/s, and large
# enough that the reply is visibly a cut sentence rather than an empty string.
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
    """Both of the port's answers, derived from one real server rather than from a transcript."""
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
    """The shipped attempt reports a capped delegated reply as unanswered.

    This runs the shipped attempt over the shipped adapter over a real server. Without the arm the
    run comes back `ok=True` carrying a cut sentence, which is the failure the whole entry is
    about. The refusal names the cap, so a reader is sent to the setting that caused it.
    """
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
