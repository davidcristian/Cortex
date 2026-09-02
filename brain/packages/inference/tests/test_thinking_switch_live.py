"""Integration: measure which request shapes this deployment honours the thinking switch on."""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

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
# Where this run's sample lands, read relative to `brain/` like every other driver's, and the
# suffix that keeps one tier's runs apart: a probe at another cap or another repeat count is a
# different reading and must not overwrite the one it was run beside.
_OUT = Path(os.environ.get("CORTEX_THINKING_OUT", "."))
_TAG = os.environ.get("CORTEX_THINKING_TAG", "")

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
    """Return the prompt this deployment's chat template makes of that request, read from it."""
    messages = [Message(role=Role.USER, text=_ASK, at=datetime.now(UTC), turn_id="t-switch")]
    bounds = GenerationBounds(max_tokens=_CAP, thinking=not switch)
    payload = build_payload(_MODEL, messages, (), schema, bounds)
    response = await client.post(f"{_ENDPOINT}/apply-template", json=payload)
    response.raise_for_status()
    prompt = response.json()["prompt"]
    assert isinstance(prompt, str)
    return prompt


async def _read_prompts(client: httpx.AsyncClient) -> dict[bool, str]:
    """Read what the template makes of the four request shapes, before any token is decoded."""
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
    return {False: plain, True: switched}


def _write(prompts: dict[bool, str], draws: dict[tuple[str, bool], list[_Cell]]) -> Path:
    """Record this run as one sample: what was rendered, and what each cell then did."""
    _OUT.mkdir(parents=True, exist_ok=True)
    path = _OUT / f"switch-{_MODEL}{_TAG}.json"
    sample = {
        "model": _MODEL,
        "endpoint": _ENDPOINT,
        "cap": _CAP,
        "ask": _ASK,
        "renderings": [{"switch": switch, "prompt": prompt} for switch, prompt in prompts.items()],
        "cells": [
            {
                "shape": shape,
                "constrained": dict(_SHAPES)[shape] is not None,
                "switch": switch,
                "draws": len(cells),
                "deliberated": sum(1 for cell in cells if cell.reasoning_chars > 0),
            }
            for (shape, switch), cells in draws.items()
        ],
    }
    path.write_text(json.dumps(sample, indent=2) + "\n", encoding="utf-8")
    return path


async def test_which_request_shapes_this_tier_honours_the_thinking_switch_on() -> None:
    """Draw four cells: two request shapes, each sent with the switch and without it."""
    print(  # noqa: T201
        f"\n{_MODEL} at {_ENDPOINT}, cap {_CAP}, {_REPEATS} draws a cell, "
        f"no server-side reasoning flags:"
    )
    draws: dict[tuple[str, bool], list[_Cell]] = {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None)) as client:
        prompts = await _read_prompts(client)
        for shape, schema in _SHAPES:
            for switch in (False, True):
                cells = [await _run(client, shape, schema, switch=switch) for _ in range(_REPEATS)]
                draws[shape, switch] = cells

    # Written before the assertions below, so a run that trips one still leaves the sample it
    # measured. Resolved rather than as written: `_OUT` is read relative to `brain/` and the line
    # below is pasted into a shell that is somewhere else.
    written = _write(prompts, draws).resolve()
    print(  # noqa: T201 -- the report IS the measurement
        f"\nwrote one sample: {written}\n"
        "  the rendering above predicts the constrained cell, and nothing here checks it:\n"
        f"  just switch-tail {written}"
    )
    print()  # noqa: T201
    for shape, _ in _SHAPES:
        control, switched = draws[shape, False], draws[shape, True]
        quiet = [cell for cell in control if cell.reasoning_chars == 0]
        assert not quiet, (
            f"{len(quiet)} of {_REPEATS} {shape} draws deliberated not at all with the switch left "
            f"alone, so this run says nothing about the switch: either this prompt invites no "
            f"thought on {_MODEL} or its template renders the thought closed whatever the key "
            f"says, and `just switch-tail {written}` reads the rendering to say which"
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
