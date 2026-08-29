"""Integration: does this deployment's engine read a per-request trace budget, and does it hold?

`GenerationBounds(trace_tokens=N)` renders as llama.cpp's `reasoning_budget_tokens` and is the
half of the thinking lever that a request shape cannot overrule (ADR-0005 request-lever addendum).
Two things have to be true for it to be worth sending, and this file measures both against a real
server rather than believing either:

1. the engine **parses** the key, which `reads_a_trace_budget` answers off one refused request and
   which is what `CORTEX_INFERENCE_TRACE_LEVER=auto` believes at wiring;
2. the count then **holds** on the request shape the thinking switch loses, a constrained reply
   into the fixed envelope, which is what the cells below draw.

Point it at any llama-server:

    cd brain && CORTEX_TRACE_ENDPOINT=http://127.0.0.1:8082 \\
      uv run pytest -m integration --no-cov -s \\
      packages/inference/tests/test_trace_budget_live.py

The server must be started with **no** `--reasoning-budget` and **no** `--chat-template-kwargs`,
for the reason its sibling `test_thinking_switch_live.py` needs the same: a tier that ends every
thought at once shows no trace whichever way a request is read, which is the right way to run a
subagent tier and the wrong way to measure one.

**Three cells and only the first is asserted.** A request carrying neither lever must deliberate
on every draw, or this prompt invites no thought here and the run is thrown away rather than read.
The other two are the levers, and they are rates rather than verdicts: the first version of this
file asserted that the switch fails, and failed on the tier it was measuring, because on that pick
the switch is a coin toss rather than a defect that reproduces.

Measured 2026-08-29 by the agent on `ghcr.io/ggml-org/llama.cpp:server` reporting
`b10666-4e97ac86e`, the shipped subagent pick (gemma-4-E4B QAT q4_0, `-ngl 0 -c 8192`), a cap of
256 and a constrained reply into the fixed envelope, in two runs of 20 and 5 draws:

| cell | deliberated | reply |
| --- | --- | --- |
| control, neither lever | 5/5 | empty and capped on all 5 |
| the switch alone | **17/20**, and 4/5 on a later five | empty and capped on every one |
| the switch and `trace_tokens=0` | **0/20**, and 0/5 | the envelope |

The middle row is the defect, and it is why a cap paired with the switch alone is not safe on this
pick: those draws spent the whole cap on a trace nobody reads and returned nothing. The last row is
the repair. The middle row's own 4 draws in 25 that held are the reason this file asserts nothing
about it.

**The leak, which is the last row's own residue.** Forcing the end of a thought lands after its
start sequence, so what the model had written of the tag can survive into the answer. One draw of
the last row returned `{"reply": "thought"}`: a whole, valid envelope whose entire answer is the
channel name the forcing landed inside of. Across every budgeted draw of that session it is **1
of 58**, and it did **not** appear in 20 draws of the same request against a tier carrying
`--reasoning-budget 0` on its argv instead, which is what every subagent server this repo ships
already does. Those two are the same sampler, and at these sizes the two counts do not separate,
so the honest reading is one rare phenomenon rather than something the request key introduced.

What it costs is worth saying plainly, because it is worse than a refusal: the envelope is
well formed, so nothing downstream rejects it, and a delegated run reports `thought` as the
subtask's answer. The count printed below is a suspicion and not a proof, for the reasons on
`_Draw.leaked`.
"""

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
# Generous rather than snug, for the switch probe's reason: what is read is whether a trace ran at
# all, and a cap tight enough to cut one leaves every cell looking the same.
_CAP = int(os.environ.get("CORTEX_TRACE_MAX_TOKENS", "256"))
# How many draws the budgeted cell is. One by default so the command above answers in a coffee
# break; anything quoted as a tier's behaviour is drawn five or more, and the leak count wants
# twenty, being a rate rather than a verdict.
_REPEATS = int(os.environ.get("CORTEX_TRACE_REPEATS", "1"))

# The same deliberation-inviting question the switch probe asks, deliberately: the two files
# measure two levers on one cell, and a different prompt would make their tables incomparable.
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
        """Whether this draw looks like a forced end of thought that left its own tag behind.

        **Two readings, because the leak turned out to have two shapes and each detector alone
        missed one.** Text ahead of the payload is the obvious one. The other is a whole, valid
        envelope whose answer is a single word, which is what a real draw returned:
        `{"reply": "thought"}`, the channel name the forcing landed inside of, delivered as the
        subtask's answer.

        Neither is a proof and this is a probe rather than a gate, so both are printed rather than
        asserted on. The one-word reading is sound for **this** prompt and only for it: a bill
        split three ways cannot be answered in one word, so a one-word answer here is a defect
        whatever produced it. A file that asked the same of an arbitrary subtask would be wrong.

        What it deliberately does not do is look for a marker. Which token survives belongs to the
        deployment's own chat template (`<|channel>thought` on one family here, `<think>` on the
        other) and no test in this package may know one.

        The history is worth keeping, because both wrong answers were confident. The first draft
        asked whether the reply **parsed**, and called a reply cut at `max_tokens` a leak, 2 of 5
        on a cell where nothing had leaked. The second asked only about position, and reported 0
        of 20 on the run whose fifth draw is quoted above.
        """
        if self.reply and not self.reply.lstrip().startswith("{"):
            return True
        body = self.answer.strip()
        return bool(body) and len(body.split()) == 1


async def _draw(backend: LlamaCppBackend, bounds: GenerationBounds) -> _Draw:
    """One constrained completion through the shipped adapter, both halves counted."""
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
    """One cell, drawn ``_REPEATS`` times, printed as it goes."""
    print(f"{label}, {_REPEATS} draws:")  # noqa: T201
    return [await _draw(backend, bounds) for _ in range(_REPEATS)]


def _verdict(label: str, draws: list[_Draw]) -> None:
    """What a cell did, in the two counts this file exists to report."""
    thought = sum(1 for drawn in draws if drawn.deliberated)
    leaked = sum(1 for drawn in draws if drawn.leaked)
    print(  # noqa: T201
        f"{label:<26} deliberated on {thought} of {_REPEATS}, "
        f"{leaked} reply(s) look like a leaked tag"
    )


async def test_a_per_request_trace_budget_reaches_the_shape_the_switch_loses() -> None:
    """The capability read, then three cells of one request shape, through the shipped adapter.

    **Only the first cell is asserted, and it is the one that must fire.** A request carrying
    neither lever has to deliberate on every draw, or this prompt invites no thought on this tier
    (or the tier already bounds its own trace) and nothing below means anything. The other two are
    printed, because both of their answers are real deployments and this file cannot know which it
    was pointed at.

    The middle cell is the defect and **it is not asserted on purpose**, which the first version
    of this file got wrong by treating it as the control: the switch is a coin toss on the pick
    this was written against, holding on 3 draws in 20, so a run that demanded it fail every time
    would fail on the tier it was measuring. What a coin toss owes a reader is a rate.
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None)) as client:
        lever = await reads_a_trace_budget(_ENDPOINT, _MODEL, client)
    print(f"\n{_MODEL} at {_ENDPOINT}: engine reads a per-request trace budget: {lever}")  # noqa: T201
    if not lever:
        # Said out loud rather than left for a reader to work out. With no lever the adapter sends
        # no key, so the last cell is the middle one drawn again and a budget that "did not hold"
        # is a build that never saw one.
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
