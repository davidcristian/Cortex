import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import httpx
import pytest

from cortex_core import (
    GenerationBounds,
    Message,
    ReasoningChunk,
    Role,
    SingleResidentModelManager,
    TextChunk,
)
from cortex_core.subagent_reply import REPLY_ENVELOPE
from cortex_inference import LlamaCppBackend, reads_a_trace_budget

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_ENDPOINT = os.environ.get("CORTEX_TRACE_ENDPOINT", "http://127.0.0.1:8080")
_MODEL = os.environ.get("CORTEX_TRACE_MODEL", "cortex")
# Generous rather than snug, for the switch probe's reason: what is read is whether a trace ran
# at all, and a cap tight enough to cut one leaves every cell looking the same.
_CAP = int(os.environ.get("CORTEX_TRACE_MAX_TOKENS", "256"))
_REPEATS = int(os.environ.get("CORTEX_TRACE_REPEATS", "1"))

# The same question the switch probe asks, deliberately: the two files measure two settings on
# one cell, and a different prompt would make their tables incomparable.
_ASK = (
    "Three friends split a bill. Ana pays twice what Bo pays, and Cy pays 4 less than Ana. "
    "The bill is 51. What does each of them pay?"
)


@dataclass
class _Draw:
    """One completion, and the two things a budgeted request has to get right."""

    reply: str = ""
    trace_chars: int = 0
    wall_s: float = 0.0

    @property
    def deliberated(self) -> bool:
        return self.trace_chars > 0

    @property
    def answer(self) -> str:
        """The envelope's own `reply`, or the whole text where it is not an envelope."""
        try:
            envelope: object = json.loads(self.reply)
        except json.JSONDecodeError:
            return self.reply
        if not isinstance(envelope, dict):
            return self.reply
        wrapped: object = cast("dict[str, object]", envelope).get("reply")
        return wrapped if isinstance(wrapped, str) else self.reply

    @property
    def leaked(self) -> bool:
        """Whether this draw looks like a forced end of thought that left its own tag behind."""
        if self.reply and not self.reply.lstrip().startswith("{"):
            return True
        body = self.answer.strip()
        return bool(body) and len(body.split()) == 1


async def _draw(backend: LlamaCppBackend, bounds: GenerationBounds) -> _Draw:
    """Run one constrained completion through the shipped adapter, counting both halves."""
    drawn = _Draw()
    messages = [Message(role=Role.USER, text=_ASK, at=datetime.now(UTC), turn_id="t-trace")]
    started = time.monotonic()
    stream = backend.stream(_MODEL, messages, schema=REPLY_ENVELOPE, bounds=bounds)
    async for event in stream:
        if isinstance(event, TextChunk):
            drawn.reply += event.text
        elif isinstance(event, ReasoningChunk):
            drawn.trace_chars += len(event.text)
    drawn.wall_s = time.monotonic() - started
    print(  # noqa: T201 -- the report IS the measurement
        f"  trace {drawn.trace_chars:>5}  reply {len(drawn.reply):>5}  {drawn.wall_s:5.1f} s  "
        f"{'LEAKED ' if drawn.leaked else ''}{drawn.reply[:60]!r}"
    )
    return drawn


async def _arm(backend: LlamaCppBackend, label: str, bounds: GenerationBounds) -> list[_Draw]:
    """Draw one cell ``_REPEATS`` times, printing each draw as it arrives."""
    print(f"{label}, {_REPEATS} draws:")  # noqa: T201
    return [await _draw(backend, bounds) for _ in range(_REPEATS)]


def _verdict(label: str, draws: list[_Draw]) -> None:
    """Print what a cell did, in the two counts this file exists to report."""
    thought = sum(1 for drawn in draws if drawn.deliberated)
    leaked = sum(1 for drawn in draws if drawn.leaked)
    print(  # noqa: T201
        f"{label:<26} deliberated on {thought} of {_REPEATS}, "
        f"{leaked} reply(s) look like a leaked tag"
    )


async def test_a_per_request_trace_budget_reaches_the_shape_the_switch_loses() -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None)) as client:
        lever = await reads_a_trace_budget(_ENDPOINT, _MODEL, client)
    print(f"\n{_MODEL} at {_ENDPOINT}: engine reads a per-request trace budget: {lever}")  # noqa: T201
    if not lever:
        print("  so the last cell is the middle one again, and says nothing about a budget")  # noqa: T201
    manager = SingleResidentModelManager(_MODEL, _ENDPOINT)
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None)) as client:
        backend = LlamaCppBackend(manager, client, trace_lever=lever)
        control = await _arm(backend, "control, neither lever", GenerationBounds(max_tokens=_CAP))
        switched = await _arm(
            backend, "the switch alone", GenerationBounds(max_tokens=_CAP, thinking=False)
        )
        budgeted = await _arm(
            backend,
            "the switch and a budget of 0",
            GenerationBounds(max_tokens=_CAP, thinking=False, trace_tokens=0),
        )
    quiet = [drawn for drawn in control if not drawn.deliberated]
    assert not quiet, (
        f"{len(quiet)} of {_REPEATS} control draws deliberated not at all, so this tier already "
        f"bounds its trace (a --reasoning-budget on its argv) or this prompt invites no thought "
        f"on {_MODEL}, and this run says nothing about either lever"
    )
    print()  # noqa: T201
    _verdict("control, neither lever", control)
    _verdict("the switch alone", switched)
    _verdict("the switch and a budget", budgeted)
