"""Integration: on which request shapes does this deployment honour the port's thinking switch?"""

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
from cortex_inference.request import build_payload

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
_REPEATS = int(os.environ.get("CORTEX_THINKING_REPEATS", "1"))

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


async def _rendered(client: httpx.AsyncClient, schema: JsonSchema | None, *, switch: bool) -> str:
    """The prompt this deployment's own chat template makes of that request, asked not inferred."""
    messages = [Message(role=Role.USER, text=_ASK, at=datetime.now(UTC), turn_id="t-switch")]
    bounds = GenerationBounds(max_tokens=_CAP, thinking=not switch)
    payload = build_payload(_MODEL, messages, (), schema, bounds)
    response = await client.post(f"{_ENDPOINT}/apply-template", json=payload)
    response.raise_for_status()
    prompt = response.json()["prompt"]
    assert isinstance(prompt, str)
    return prompt


async def _read_prompts(client: httpx.AsyncClient) -> None:
    """What the template does with each of the four request shapes, before any token is decoded."""
    for switch in (False, True):
        prompts = {
            shape: await _rendered(client, schema, switch=switch) for shape, schema in _SHAPES
        }
        rendered = set(prompts.values())
        assert len(rendered) == 1, (
            f"the request shapes render different prompts with the switch "
            f"{'sent' if switch else 'left alone'}, so a difference between their cells below is "
            f"a difference of prompt rather than of what a schema does: {prompts}"
        )
    plain, switched = (
        await _rendered(client, None, switch=False),
        await _rendered(client, None, switch=True),
    )
    reads = "reads" if plain != switched else "IGNORES"
    print(f"template  {reads} the switch ({len(plain)} chars against {len(switched)})")  # noqa: T201
    print("shapes    render one prompt per switch, so the schema never reaches the template")  # noqa: T201


async def test_which_request_shapes_this_tier_honours_the_thinking_switch_on() -> None:
    """Four cells, each drawn ``CORTEX_THINKING_REPEATS`` times: two request shapes, each sent
    with the switch and without it.
    """
    print(  # noqa: T201
        f"\n{_MODEL} at {_ENDPOINT}, cap {_CAP}, {_REPEATS} draws a cell, "
        f"no server-side reasoning flags:"
    )
    draws: dict[tuple[str, bool], list[_Cell]] = {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None)) as client:
        await _read_prompts(client)
        for shape, schema in _SHAPES:
            for switch in (False, True):
                cells = [await _run(client, shape, schema, switch=switch) for _ in range(_REPEATS)]
                draws[shape, switch] = cells

    print()  # noqa: T201
    for shape, _ in _SHAPES:
        control, switched = draws[shape, False], draws[shape, True]
        quiet = [cell for cell in control if cell.reasoning_chars == 0]
        assert not quiet, (
            f"{len(quiet)} of {_REPEATS} {shape} draws deliberated not at all with the switch left "
            f"alone, so this prompt invites no thought on {_MODEL} and this run says nothing "
            f"about the switch"
        )
        thought = sum(1 for cell in switched if cell.reasoning_chars > 0)
        verdict = (
            "holds"
            if thought == 0
            else "does nothing"
            if thought == _REPEATS
            else f"holds on {_REPEATS - thought} of {_REPEATS} draws"
        )
        print(f"{shape:<9} the switch {verdict} on {_MODEL}")  # noqa: T201
    served = [cell for cells in draws.values() for cell in cells]
    assert all(cell.tokens is not None for cell in served), (
        f"a cell reported no timings, so it was not served: "
        f"{[c.line() for c in served if c.tokens is None]}"
    )
