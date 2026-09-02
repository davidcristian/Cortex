"""Integration: measure which request shapes this deployment honours the thinking switch on.

`GenerationBounds(thinking=False)` renders as `chat_template_kwargs: {"enable_thinking": false}`
(ADR-0005), and whether the model then skips its deliberation is not the caller's to know. It is
decided behind the endpoint, and measured here it is decided **per request shape**: on one shipped
pick the switch holds whatever the request carries, and on the other it holds on a plain request
and mostly does nothing on one carrying a `response_format`.

That matters because four shipped `GenerationBounds` pair a cap sized on the wanted answer with
that switch, and one of them (the recall rank's) carries a schema too. On a shape where the switch
does nothing, such a pair deletes the reply rather than shortening it: the model spends the whole
cap thinking and the answer never starts. So this is the probe a deployment runs to learn which of
its
own shapes are safe, and it is the reading the ADR-0005 switch-is-advisory addendum is made of.
Point it at any llama-server:

    cd brain && CORTEX_THINKING_ENDPOINT=http://127.0.0.1:8080 \\
      CORTEX_THINKING_REPEATS=5 CORTEX_THINKING_OUT=../measurements \\
      uv run pytest -m integration --no-cov -s \\
      packages/inference/tests/test_thinking_switch_live.py

It writes one sample per tier (`CORTEX_THINKING_OUT`, `CORTEX_THINKING_TAG`), naming the engine
build and the model file the server reported of itself on `GET /props`, and judges nothing about
the rendering it took. `just switch-tail <sample>` is what reads the rendered prompt back
against the cells, and the run prints the line to paste; the split is `scripts/switchtail.py`'s
docstring and it is the envelope harness's, a claim's arithmetic belonging in a covered file rather
than in an integration-marked driver no gate runs.

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

**One draw is not enough to report a cell.** `CORTEX_THINKING_REPEATS` sets how many times each
cell is
drawn. It defaults to 1 so the command above still answers in a coffee break, and a number quoted
anywhere as a tier's behaviour is drawn 5 times or more, because the first reading of the subagent
row below was a single draw of a cell that turns out to split 4 to 1.

Measured 2026-08-28 by the agent at 5 draws a cell, both tiers this repo ships, each server started
with neither flag on llama.cpp `b10644-d7a207411`, at a cap of 256, each cell counting the draws
that deliberated:

| tier | plain, no switch | plain, switch | envelope, no switch | envelope, switch |
| --- | --- | --- | --- | --- |
| cortex, gemma-4-12B QAT q4_0, `-ngl 99` | 5/5 | 0/5 | 5/5 | **0/5** |
| subagent, gemma-4-E4B QAT q4_0, `-ngl 0` | 5/5 | 0/5 | 5/5 | **4/5** |

The two right-hand columns are the finding. Both picks honour the switch on a plain request, and
under the envelope the E4B mostly deliberates through it and spends the whole cap doing so, which
is the capped empty reply a delegated run was reaching the cortex with.

**Every other chat entry of the lineup (ADR-0004) was asked the same way on the same build**, and
the per-entry table is the ADR-0005 addendum's lineup section. Two of its readings matter to anyone
pointing this file at a server. Nothing in the lineup ignores the switch on a **plain** request, so
a verdict of "does nothing" there is news about a deployment rather than a known pick. And under the
envelope the split belongs to the **template** rather than to the family or the handler: the two
gemma-4-E entries are the only ones that deliberate through the switch, the dense gemma-4 entries
and every Qwen entry hold, and on all of them the verdict is the one the rendered-prompt line below
predicts. A template that answers the switch by rendering a thought already closed holds under a
schema; a template that answers it by dropping the block and adding nothing does not.

**Why the split falls there, which is what the rendered-prompt lines this probe prints ahead of
the cells show.** A `response_format` does not change the chat format and does not reach the
template at all; what it changes is that llama.cpp
builds a grammar, and the gemma-4 handler's root for one is a start, then an optional thought, then
the fenced JSON payload: it leaves the model's reasoning channel open as the only continuation that
admits prose. The other handler this lineup resolves to, `peg-native`, builds the same shape with
`<think>` and `</think>` where the gemma one writes its channel markers, so neither handler here
closes that continuation. It builds that alternative without reading `enable_thinking`, so on a
constrained request the switch's
only lever is whatever the template itself renders, and the two picks differ there: the cortex's
answers "do not think" by opening and closing an empty thought in the prompt, and the E4B's by
dropping a marker and adding nothing. The full account is in the ADR-0005 switch-is-advisory
addendum's mechanism section; the grammar itself is not on any endpoint, and is read by starting
the server with `--verbose` and grepping its log for `Grammar` and `chat format:`.

That last rule is a **prediction over one engine build's handlers** rather than a theorem, and a
handler that gated its reasoning rule on `enable_thinking`, which sibling handlers in the same file
already do, would break it. This run therefore records the rendering it took beside the cells it
drew, and `just switch-tail` says whether the two still agree, so a tier that breaks the rule is
named and measured rather than left contradicting a wall of prose two documents carry.
"""

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
# How many draws each cell is. Sampling here is the server's own default, so one draw is one
# sample of a distribution and not a reading of it: the entry this file's addendum came from was
# closed the first time on a single draw that happened to say the wrong thing. The default stays
# 1 so the runbook's one-command form still answers in a coffee break, and anything reported as a
# tier's behaviour is run at 5 or more.
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
    """Return the prompt this deployment's chat template makes of that request, read from it.

    ``POST /apply-template`` runs the template over the body the adapter would have sent and hands
    back the text the model will really see, which is the one half of the engine's side that is
    readable over HTTP. It separates the two things a silent switch can mean, a key that never
    reached the template and a template that read it and a model that deliberated anyway, and it
    is what says a difference between the two request shapes is not a difference in their prompts.
    """
    messages = [Message(role=Role.USER, text=_ASK, at=datetime.now(UTC), turn_id="t-switch")]
    bounds = GenerationBounds(max_tokens=_CAP, thinking=not switch)
    payload = build_payload(_MODEL, messages, (), schema, bounds)
    response = await client.post(f"{_ENDPOINT}/apply-template", json=payload)
    response.raise_for_status()
    prompt = response.json()["prompt"]
    assert isinstance(prompt, str)
    return prompt


@dataclass(frozen=True)
class _Server:
    """What the server said of itself on ``GET /props``: the engine build and the file it loaded."""

    build_info: str
    model_path: str


async def _served(client: httpx.AsyncClient) -> _Server:
    """Read which engine build and which model file are answering, once, before anything runs.

    `_MODEL` is whatever the operator typed, and a row quoted from this run is quoted under a build
    and a quant. Both are the server's to report, so they are read off it and written into the
    sample under the names `/props` gives them, rather than copied off the driver's notes.
    """
    response = await client.get(f"{_ENDPOINT}/props")
    response.raise_for_status()
    props: dict[str, object] = response.json()
    build_info, model_path = props.get("build_info"), props.get("model_path")
    assert isinstance(build_info, str), (
        f"GET /props at {_ENDPOINT} names no build_info, so this run cannot say which engine "
        f"build served it: {sorted(props)}"
    )
    assert isinstance(model_path, str), (
        f"GET /props at {_ENDPOINT} names no model_path, so this run cannot say which file "
        f"served it: {sorted(props)}"
    )
    print(f"server    {build_info} serving {model_path}")  # noqa: T201
    return _Server(build_info, model_path)


async def _read_prompts(client: httpx.AsyncClient) -> dict[bool, str]:
    """Read what the template makes of the four request shapes, before any token is decoded.

    Two readings come out of it. The schema must not reach the template at all, meaning the two
    shapes carrying the same switch render the same prompt; that is asserted, because a tier where
    it fails is a tier whose four cells are comparing two different prompts and whose verdict below
    would name the wrong cause. Whether the **switch** reaches the template is printed rather than
    asserted, both answers being real deployments, and it is the line to read first when a verdict
    says the switch holds: a template that never read the key cannot be why a trace stopped.

    Both renderings are returned rather than only reported, because the rule that reads the
    constrained verdict off them is held by `scripts/switchtail.py` over the sample this run
    writes, and a rendering this run did not keep could not be checked at all.
    """
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


def _write(
    server: _Server, prompts: dict[bool, str], draws: dict[tuple[str, bool], list[_Cell]]
) -> Path:
    """Record this run as one sample: what served it, what was rendered, and what each cell did.

    The counting stops here. Whether the rendering predicted the constrained verdict is
    `scripts/switchtail.py`'s to say, for the reason the envelope harness leaves its rates to
    `scripts/envelopefloor.py`: this file is integration-marked and no gate runs a line of it, so
    a rule asserted here would be a rule no gate ever runs. Which cell carried a schema and which
    sent the switch travel as the sample's own flags, so the reader needs no shape's name.
    """
    _OUT.mkdir(parents=True, exist_ok=True)
    path = _OUT / f"switch-{_MODEL}{_TAG}.json"
    sample = {
        "model": _MODEL,
        "endpoint": _ENDPOINT,
        "build_info": server.build_info,
        "model_path": server.model_path,
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
    """Draw four cells: two request shapes, each sent with the switch and without it.

    Each cell is drawn ``CORTEX_THINKING_REPEATS`` times. What comes out is a verdict per shape,
    plus the control that makes it a measurement rather than an anecdote: a request that sent no
    switch must have deliberated, or nothing here is about the switch, whether because this prompt
    invites no thought on this tier or because its template renders the thought closed whatever
    the key says, which `scripts/switchtail.py` reads off the sample. Every draw of that arm has
    to deliberate, because a cell is a set of samples from a sampling model, and accepting one
    convenient draw is how the reading before this one went wrong.

    The verdicts are printed and not asserted, because both answers are real deployments and this
    file cannot know which one it is pointed at. What it asserts besides the control is that every
    cell was really served, a completion with no timings being a cell that says nothing.
    """
    print(  # noqa: T201
        f"\n{_MODEL} at {_ENDPOINT}, cap {_CAP}, {_REPEATS} draws a cell, "
        f"no server-side reasoning flags:"
    )
    draws: dict[tuple[str, bool], list[_Cell]] = {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None)) as client:
        server = await _served(client)
        prompts = await _read_prompts(client)
        for shape, schema in _SHAPES:
            for switch in (False, True):
                cells = [await _run(client, shape, schema, switch=switch) for _ in range(_REPEATS)]
                draws[shape, switch] = cells

    # Written before the assertions below, so a run that trips one still leaves the sample it
    # measured. Resolved rather than as written: `_OUT` is read relative to `brain/` and the line
    # below is pasted into a shell that is somewhere else.
    written = _write(server, prompts, draws).resolve()
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
