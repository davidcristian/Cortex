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
    async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S) as client:
        probe = PropsVisionProbe(_ENDPOINT or "", client)
        await probe.can_see()
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
