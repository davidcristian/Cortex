"""What a generated session title costs the turn it rides on, before and after it was bounded.

Integration-marked: excluded from CI and the coverage gate by the workspace addopts
(`-m "not integration"`). Needs the gpu stack for the resident cortex:

    cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 \
      uv run pytest -m integration --no-cov packages/inference/tests/test_session_title_live.py -s

The title pass is the second of the two in-turn side calls whose thinking `drain_text` throws
away (the history recap was the first, `test_history_recap_live.py`). It runs at the end of a
session's first turn, between the reply and `TurnCompleted`, so what it costs is time the user
waits with the answer already on screen and nothing else happening.

Two arms. The first prices the shipped prompt with `bounds=None`, which is the request this pass
sent before it was bounded, against `TITLE_BOUNDS`, which is what it sends now, over the identical
prompt. The second runs the shipped cap with thinking left ON, the trap the cap and the switch
ship together to avoid; here it is not the recap's coin flip, because a title is a few tokens and
the deliberation before it is hundreds.

`-s` is required: the print IS the measurement.
"""

import os
import time
from datetime import UTC, datetime

import httpx
import pytest

from cortex_core import (
    TITLE_BOUNDS,
    Message,
    SingleResidentModelManager,
    build_title_messages,
    clean_title,
)
from cortex_core.drain import drain_text
from cortex_core.inference import GenerationBounds
from cortex_inference import LlamaCppBackend

_MODEL = os.environ.get("CORTEX_MODEL_CORTEX", "cortex")
_ENDPOINT = os.environ.get("CORTEX_INFERENCE_ENDPOINT", "http://127.0.0.1:8080")
_AT = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)

# How many times each side of the pricing arm repeats. Small, like the recap's: the point is a
# ratio of several times over, not a tight interval, and the unbounded side is the slow one.
_PRICING_RUNS = 3

# One session's opening exchange, of the shape the engine hands this pass: the user's first
# message and the reply that was just persisted.
_USER = "how do cats decide where to sleep during the day?"
_ASSISTANT = (
    "Cats pick sleeping spots for warmth, safety and a view of the room: a sunny patch, a high "
    "shelf, or anywhere they can see the door. They rotate through favourites as the sun moves."
)


def _title_prompt() -> list[Message]:
    return build_title_messages(_USER, _ASSISTANT, at=_AT, turn_id="t1")


@pytest.mark.integration
async def test_the_title_costs_less_once_it_stops_paying_for_thinking_nobody_reads() -> None:
    """The before and after over the identical prompt, through the shipped adapter.

    ``bounds=None`` is exactly the request the title pass sent before it was bounded: no cap, and
    whatever the server's chat template does about thinking, which for the cortex is think first.
    ``TITLE_BOUNDS`` is what it sends now. Everything else is held constant.

    What is asserted is what a turn depends on: every bounded run still produced a title the
    engine would persist (a non-empty ``clean_title`` is the same gate the engine applies), and
    the bounded arm is cheaper in total. The per-run seconds are printed rather than asserted,
    because pinning a model's speed pins the model.
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        prompt = _title_prompt()
        timings: dict[str, list[float]] = {"unbounded": [], "bounded": []}
        titles: dict[str, list[str]] = {"unbounded": [], "bounded": []}
        for _ in range(_PRICING_RUNS):
            for label, bounds in (("unbounded", None), ("bounded", TITLE_BOUNDS)):
                started = time.monotonic()
                raw = await drain_text(backend, _MODEL, prompt, bounds=bounds)
                timings[label].append(time.monotonic() - started)
                titles[label].append(clean_title(raw))
        print(  # noqa: T201 -- the measurement IS this test's output
            f"\nunbounded (the request that shipped): "
            f"{[round(s, 1) for s in timings['unbounded']]} s, titles {titles['unbounded']}"
            f"\nbounded ({TITLE_BOUNDS}): "
            f"{[round(s, 1) for s in timings['bounded']]} s, titles {titles['bounded']}"
        )
        # Every bounded run produced a title the engine would actually store.
        assert all(titles["bounded"])
        assert sum(timings["bounded"]) < sum(timings["unbounded"])


@pytest.mark.integration
async def test_a_cap_against_a_thinking_model_deletes_the_title_it_was_sized_for() -> None:
    """Why the cap does not ship on its own, with the number that says so.

    A reasoning model spends its budget deliberating BEFORE it answers, so a cap sized from a
    four-token title is reached with nothing said. Unlike the recap's cap this is not a coin
    flip: the deliberation is two orders of magnitude longer than the answer. The outcome is
    still reported rather than asserted, because it is a model behaviour; what is asserted is
    the pairing at the same cap, so the run cannot be read as a bad day for the model.
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        prompt = _title_prompt()
        capped = GenerationBounds(max_tokens=TITLE_BOUNDS.max_tokens, thinking=True)
        raw = await drain_text(backend, _MODEL, prompt, bounds=capped)
        print(  # noqa: T201 -- the measurement IS this test's output
            f"\nthinking on, capped at {capped.max_tokens}:"
            f" {len(raw)} chars of reply, usable: {bool(clean_title(raw))}"
        )
        paired = await drain_text(backend, _MODEL, prompt, bounds=TITLE_BOUNDS)
        assert clean_title(paired)
