"""Integration: the vision probe against a real ``llama-server``, and what it costs a turn.

The fakes prove the logic; this proves the adapter reads a real server's `/props` and that
asking per turn is affordable, which is the measurement the whole design rests on. Nothing here
runs in CI or under the coverage gate (`integration`-marked, AGENTS.md gate 3).

Bring up the GPU stack (`docs/runbooks/llamacpp-gpu.md`) with a projector named in the repo-root
`.env`, then:

    cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 \\
      uv run pytest -m integration --no-cov -s packages/orchestrator/tests/test_vision_live.py

Validated 2026-08-06 on the 24 GB card against gemma-4-12B + its projector: the probe answered
True, and 40 samples cost 1.5 ms at the median idle and 1.7 ms with a generation in flight, worst
2.5 ms. The half a test cannot stage from here is the projector going away, which needs the model
host recreated without `CORTEX_MMPROJ_FILE_CORTEX`; that procedure and its result are in
`docs/runbooks/vision.md`.
"""

import os
import statistics
import time

import httpx
import pytest

from cortex_orchestrator.vision import PROBE_TIMEOUT_S, PropsVisionProbe

_ENDPOINT = os.environ.get("CORTEX_INFERENCE_ENDPOINT")
_SAMPLES = 20

pytestmark = pytest.mark.skipif(
    not _ENDPOINT, reason="needs CORTEX_INFERENCE_ENDPOINT (a running llama-server)"
)


@pytest.mark.integration
async def test_the_probe_reads_a_real_servers_modalities() -> None:
    """Whatever this deployment loaded, the probe and the server agree about it."""
    async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S) as client:
        probe = PropsVisionProbe(_ENDPOINT or "", client)
        answer = await probe.can_see()
        raw = (await client.get(f"{(_ENDPOINT or '').rstrip('/')}/props")).json()

    assert answer is (raw.get("modalities", {}).get("vision") is True)
    print(  # noqa: T201
        f"\nlive /props modalities: {raw.get('modalities')}, probe answered {answer}"
    )


@pytest.mark.integration
async def test_asking_every_turn_costs_a_turn_nothing_measurable() -> None:
    """The number the per-call design rests on: a probe is noise beside a capture.

    A screen read blits a display, downscales it and PNG-encodes it; if a `/props` were anywhere
    near that, caching would have to come back with all the staleness it carries.
    """
    async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S) as client:
        probe = PropsVisionProbe(_ENDPOINT or "", client)
        await probe.can_see()  # warm the connection; the pool is shared for the process's life
        elapsed: list[float] = []
        for _ in range(_SAMPLES):
            started = time.perf_counter()
            await probe.can_see()
            elapsed.append((time.perf_counter() - started) * 1000)

    median = statistics.median(elapsed)
    print(  # noqa: T201
        f"\nprobe latency over {_SAMPLES}: median {median:.2f} ms, worst {max(elapsed):.2f} ms"
    )
    assert median < 100, "a per-turn probe has to be free, or the design owes a cache again"
    assert max(elapsed) * 1000 < PROBE_TIMEOUT_S * 1_000_000
