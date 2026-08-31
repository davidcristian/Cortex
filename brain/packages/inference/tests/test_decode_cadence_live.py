"""Integration: the decode cadence off a real llama-server, and the spill it is there to catch.

The fakes prove the parsing and the policy; this proves that a real server reports the figure at
all, and that the shipped `CadenceWatch` separates a tier that has the card from one that is
paged to host memory. That separation is the whole claim, because nothing else on the machine
makes it: an overcommitted card does not refuse the second load, both tiers report `ready`, and
free memory afterwards reads like a fit.

Integration-marked, so CI and the coverage gate never see it (AGENTS.md gate 3). It needs the GPU
stack with the model-host control API published and the deep tier named
(`just up-modelhost-loopback`, `docs/runbooks/model-swap.md`), then:

    cd brain && CORTEX_CADENCE_ENDPOINT=http://127.0.0.1:9081 \\
      uv run pytest -m integration --no-cov -s \\
      packages/inference/tests/test_decode_cadence_live.py

`CORTEX_CADENCE_FLOOR_TPS` is what the run judges against, and it is the same figure a deployment
would put in `CORTEX_SWAP_BRAIN_DECODE_TPS`. The **two arms are an operator procedure, not a
fixture**: this suite measures whatever tier is at the endpoint under whatever else is resident,
and which of those two worlds it ran in is arranged by starting or stopping the peer through the
control API. Both halves of that procedure, and the numbers they produced, are in the runbook.

Measured 2026-08-08 by the agent on the 24 GB card (RTX 5090 Laptop, 24463 MiB), gemma-4-31B QAT
q4_0 as the deep tier and gemma-4-12B QAT q4_0 as the cortex, by this suite as written:

| Arm | free | its three runs | best | at a 25.0 floor |
| --- | --- | --- | --- | --- |
| cortex resident, then deep | 423 MiB | 21.64, 20.38, 22.77 | 22.77 | **collapsed**, 2.23 short |
| deep alone, the peer evicted | 8649 MiB | 28.32, 29.82, 29.38 | 29.82 | not collapsed |

The first row is a co-resident handoff's own load order, the cortex standing and the deep model
arriving beside it, and it is the payoff: **both tiers answered `ready` in both arms**, the card
read 423 MiB free where a genuine fit reads about 900, and the only instrument that told them
apart is the one this suite drives. The second row is the same floor passing on the same tier
minutes later, which is what makes the first row's refusal readable rather than a gate that always
fires.

Two further arms the same day, through the same shipped adapter and watch driven from a script
rather than from this suite, put the spread wider than either row above. A **cold** load of the
deep tier onto a clear card reached 31.08, 31.85 and 33.78 tok/s at 2310 MiB free, and the same
overcommit measured 18.53, 18.79 and 20.32. Both effects are in that gap, and the second is worth
knowing: evicting the peer recovers a spilled tier's rate but not all of it (29.82 against 33.78
from cold), and free memory then reads 8649 MiB where the cold load read 2310, so a tier that has
spilled keeps part of itself off the card until it is reloaded. A floor is therefore set from a
cold load and read as a floor, never as a target.
"""

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
    """Run `_RUNS` completions against one tier, through the shipped adapter and watch.

    Asserts only what is true of any working tier: that the figure arrives at all, that it is
    reported once per completion, and that it is a rate a real card could produce. The verdict is
    printed rather than asserted, because which verdict is correct depends on what else the
    operator left resident, and a test that demanded one would be asserting on the procedure.
    """
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
