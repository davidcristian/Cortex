"""Integration: the decode cadence off a real llama-server, and the spill it is there to catch."""

import os
from datetime import UTC, datetime

import httpx
import pytest

from cortex_core import CadenceWatch, DecodeCadence, Message, Role, SingleResidentModelManager
from cortex_inference import LlamaCppBackend

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_ENDPOINT = os.environ.get("CORTEX_CADENCE_ENDPOINT", "http://127.0.0.1:9081")
_MODEL = os.environ.get("CORTEX_CADENCE_MODEL", "brain")
_FLOOR = float(os.environ.get("CORTEX_CADENCE_FLOOR_TPS", "25.0"))
_RUNS = int(os.environ.get("CORTEX_CADENCE_RUNS", "3"))
# Long enough that the completion clears MIN_CADENCE_TOKENS several times over, so the run is
# judging the tier rather than the first token's latency.
_PROMPT = "Explain, in about 120 words, why a GPU is fast at matrix work."
_TIMEOUT_S = 600.0


async def test_a_real_server_reports_its_decode_cadence_and_the_watch_judges_it() -> None:
    """One tier, `_RUNS` completions, through the shipped adapter and the shipped watch."""
    watch = CadenceWatch(_FLOOR)
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        for run in range(_RUNS):
            messages = [
                Message(role=Role.USER, text=_PROMPT, at=datetime.now(UTC), turn_id=f"t{run}")
            ]
            cadences = [
                event
                async for event in backend.stream(_MODEL, messages)
                if isinstance(event, DecodeCadence)
            ]
            assert len(cadences) == 1, f"expected one cadence per completion, got {cadences!r}"
            assert cadences[0].tokens_per_second > 0
            assert cadences[0].tokens > 0
            watch.observe(cadences[0])
            print(f"run {run + 1}: {cadences[0]}")  # noqa: T201 -- the measurement IS the output

    reading = watch.reading()
    assert reading is not None, "no completion was long enough to judge; raise the prompt's length"
    print(  # noqa: T201 -- the measurement IS this test's output
        f"\n{_MODEL} at {_ENDPOINT}: best {reading.observed.tokens_per_second:.2f} tok/s over "
        f"{reading.judged} of {reading.samples} samples, floor {reading.floor:.2f}, "
        f"collapsed={reading.collapsed} (short by {reading.shortfall:.2f})"
    )
