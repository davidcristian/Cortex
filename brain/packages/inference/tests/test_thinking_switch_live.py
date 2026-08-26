"""Integration: on which request shapes does this deployment honour the port's thinking switch?

`GenerationBounds(thinking=False)` renders as `chat_template_kwargs: {"enable_thinking": false}`
(ADR-0005), and whether the model then skips its deliberation is not the caller's to know. It is
decided behind the endpoint, and measured here it is decided **per request shape**: on one shipped
pick the switch holds whatever the request carries, and on the other it holds on a plain request
and does nothing at all on one carrying a `response_format`.

That matters because four shipped `GenerationBounds` pair a cap sized on the wanted answer with
that switch, and one of them (the recall rank's) carries a schema too. On a shape where the switch
does nothing, such a pair does not shorten the reply, it deletes it: the model spends the whole cap
thinking and the answer never starts. So this is the probe a deployment runs to learn which of its
own shapes are safe, and it is the reading the ADR-0005 switch-is-advisory addendum is made of.
Point it at any llama-server:

    cd brain && CORTEX_THINKING_ENDPOINT=http://127.0.0.1:8080 \\
      uv run pytest -m integration --no-cov -s \\
      packages/inference/tests/test_thinking_switch_live.py

The server must be started with **no** `--reasoning-budget` and **no** `--chat-template-kwargs`,
because both of those are the deployment answering the question for the model: a tier that ends
every thought at once shows no trace whichever way the request is read, which is the right way to
run a subagent tier and the wrong way to measure one.

**The control has to fire or there is no measurement**, which is the lesson this file exists to
carry. The switch was once "validated" on `17 + 25`, a prompt that invites no deliberation from
anything: with no trace to stop, a shape that honours the switch and one that ignores it look
identical, and a later reading of the same kind concluded the switch was dead on a template where
it is not. So the arms that send no switch must deliberate, per shape, and that is an assertion
here rather than a line to read past.

Measured 2026-08-27 by the agent, one run per cell, both tiers this repo ships, each server
started with neither flag, at a cap of 256, each cell reading trace characters then reply
characters:

| tier | plain, no switch | plain, switch | envelope, no switch | envelope, switch |
| --- | --- | --- | --- | --- |
| cortex, gemma-4-12B QAT q4_0, `-ngl 99` | 735, 0 | 0, 693 | 685, 0 | **0, 611** |
| subagent, gemma-4-E4B QAT q4_0, `-ngl 0` | 654, 0 | 0, 726 | 599, 0 | **664, 0** |

The two right-hand columns are the finding. Both picks honour the switch on a plain request, and
under the envelope the E4B deliberates through it and spends the whole cap doing so, which is the
capped empty reply a delegated run was reaching the cortex with. The cortex row is what rules out
the simplest explanation, that a `response_format` costs a request its `chat_template_kwargs`
before any template sees them: same build, same code path, and that row is silent. The full
numbers are in the addendum.
"""

import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
import pytest

from cortex_core import (
    DecodeCadence,
    DecodeStop,
    GenerationBounds,
    JsonSchema,
    Message,
    ReasoningChunk,
    Role,
    SingleResidentModelManager,
    TextChunk,
)
from cortex_core.subagent_reply import REPLY_ENVELOPE
from cortex_inference import LlamaCppBackend

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_ENDPOINT = os.environ.get("CORTEX_THINKING_ENDPOINT", "http://127.0.0.1:8080")
_MODEL = os.environ.get("CORTEX_THINKING_MODEL", "cortex")
# A cap, so a cell on a CPU tier whose trace nothing stops still ends inside a coffee break. It is
# deliberately generous rather than snug: what is being read is whether a trace ran at all, and a
# cap tight enough to cut one would leave every cell looking the same.
_CAP = int(os.environ.get("CORTEX_THINKING_MAX_TOKENS", "256"))
# How much of each trace is printed. A count says the tokens went to deliberation and cannot say
# what the model was deliberating about, and on a cell that spent its whole cap there, what it was
# writing is the difference between a model thinking and a model narrating the task.
_HEAD = int(os.environ.get("CORTEX_THINKING_HEAD", "160"))

# A question with a few steps in it, because the control has to fire. Short enough that a 4B model
# on a CPU answers inside a minute, and not a lookup: a prompt whose answer is one token invites no
# deliberation, and a probe run on one measures nothing.
_ASK = (
    "Three friends split a bill. Ana pays twice what Bo pays, and Cy pays 4 less than Ana. "
    "The bill is 51. What does each of them pay?"
)

# The two shapes a bound request is sent in here. Plain is the title, the recap and a user's own
# reply; the envelope is what a tool-less subagent decodes into (ADR-0028) and the shape the recall
# rank's own schema puts it in, and it is the one the switch was first seen doing nothing on.
_SHAPES: tuple[tuple[str, JsonSchema | None], ...] = (("plain", None), ("envelope", REPLY_ENVELOPE))


@dataclass
class _Cell:
    """One request shape, sent one way, and what the server did with it."""

    shape: str
    switch: bool
    reply_chars: int = 0
    reasoning_chars: int = 0
    ttft_s: float | None = None
    wall_s: float = 0.0
    tokens: int | None = None
    stop: str | None = None
    head: str = field(default="", repr=False)

    @property
    def label(self) -> str:
        return f"{self.shape}, {'switch' if self.switch else 'no switch'}"

    def line(self) -> str:
        first = "-" if self.ttft_s is None else f"{self.ttft_s:.1f}"
        return (
            f"{self.label:<22} ttft {first:>5} s  wall {self.wall_s:6.1f} s  "
            f"{self.tokens!s:>4} tokens  {self.stop!s:<8}  "
            f"reply {self.reply_chars:>5}  trace {self.reasoning_chars:>5}"
        )


async def _run(
    client: httpx.AsyncClient, shape: str, schema: JsonSchema | None, *, switch: bool
) -> _Cell:
    """One completion through the shipped adapter, counting both halves of what came back."""
    cell = _Cell(shape=shape, switch=switch)
    backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
    messages = [Message(role=Role.USER, text=_ASK, at=datetime.now(UTC), turn_id="t-switch")]
    bounds = GenerationBounds(max_tokens=_CAP, thinking=not switch)
    started = time.monotonic()
    async for event in backend.stream(_MODEL, messages, schema=schema, bounds=bounds):
        if isinstance(event, TextChunk):
            if cell.ttft_s is None:
                cell.ttft_s = time.monotonic() - started
            cell.reply_chars += len(event.text)
        elif isinstance(event, ReasoningChunk):
            cell.reasoning_chars += len(event.text)
            cell.head = (cell.head + event.text)[:_HEAD]
        elif isinstance(event, DecodeCadence):
            cell.tokens = event.tokens
        elif isinstance(event, DecodeStop):
            cell.stop = event.reason.value
    cell.wall_s = time.monotonic() - started
    print(f"  {cell.line()}")  # noqa: T201 -- the report IS the measurement
    if cell.head:
        print(f"    trace: {cell.head!r}")  # noqa: T201
    return cell


async def test_which_request_shapes_this_tier_honours_the_thinking_switch_on() -> None:
    """Four cells: two request shapes, each sent with the switch and without it.

    What comes out is a verdict per shape, plus the control that makes it a measurement rather than
    an anecdote: a request that sent no switch must have deliberated, or this prompt invites no
    thought on this tier and nothing here is about the switch.

    The verdicts are printed and not asserted, because both answers are real deployments and this
    file cannot know which one it is pointed at. What it asserts besides the control is that every
    cell was really served, a completion with no timings being a cell that says nothing.
    """
    print(f"\n{_MODEL} at {_ENDPOINT}, cap {_CAP}, no server-side reasoning flags:")  # noqa: T201
    cells: dict[tuple[str, bool], _Cell] = {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None)) as client:
        for shape, schema in _SHAPES:
            for switch in (False, True):
                cells[shape, switch] = await _run(client, shape, schema, switch=switch)

    print()  # noqa: T201
    for shape, _ in _SHAPES:
        control, switched = cells[shape, False], cells[shape, True]
        assert control.reasoning_chars > 0, (
            f"the {shape} arm deliberated not at all with the switch left alone, so this prompt "
            f"invites no thought on {_MODEL} and this run says nothing about the switch"
        )
        verdict = "holds" if switched.reasoning_chars == 0 else "does nothing"
        print(f"{shape:<9} the switch {verdict} on {_MODEL}")  # noqa: T201
    assert all(cell.tokens is not None for cell in cells.values()), (
        f"a cell reported no timings, so it was not served: {[c.line() for c in cells.values()]}"
    )
