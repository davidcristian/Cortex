"""Both `VisionProbe` implementations against the same checks (`vision_probe_contract.py`).

The core's `ScriptedVisionProbe` and the real `PropsVisionProbe` over a `MockTransport` client:
only the socket is faked, so the real adapter's URL building, status handling, JSON reading and
error swallowing are all exercised by the same three checks the fake passes. The live half of
the adapter (a real `llama-server` whose projector really goes away) is `test_vision_live.py`,
integration-marked per AGENTS.md gate 3.

Distrust-green proofs (each mutation applied to production code alone, `packages/orchestrator`
plus `packages/core` re-run, 2026-08-06):

- caching the first `/props` answer in `PropsVisionProbe` reddens 2, this suite's `props` arms of
  `answers_what_the_world_reports` and `re_reads_the_world_on_every_call`;
- letting the `httpx.HTTPError` escape instead of answering False reddens 4, this suite's
  `an_unanswerable_world_is_no_vision[props]` plus three cases in `test_vision.py` (a non-2xx, a
  body that is not JSON, and the `auto` builder's own dead endpoint).
"""

from collections.abc import Callable

import httpx
import pytest
from vision_probe_contract import ALL_CHECKS, Check, ProbeUnderTest

from cortex_core import ScriptedVisionProbe
from cortex_orchestrator.vision import PropsVisionProbe

type Build = Callable[[], tuple[ProbeUnderTest, httpx.AsyncClient | None]]


def _scripted() -> tuple[ProbeUnderTest, httpx.AsyncClient | None]:
    probe = ScriptedVisionProbe()
    under_test = ProbeUnderTest(
        probe=probe,
        set_vision=lambda seeing: probe.rescript([seeing]),
        break_world=lambda: probe.rescript([False]),
    )
    return under_test, None


def _props() -> tuple[ProbeUnderTest, httpx.AsyncClient | None]:
    """The real adapter over a transport whose answer a test can change between calls."""
    world = {"vision": True, "broken": False}

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://llama:8080/props", (
            "the endpoint gained a slash or lost one"
        )
        if world["broken"]:
            msg = "connection refused"
            raise httpx.ConnectError(msg)
        return httpx.Response(200, json={"modalities": {"vision": world["vision"]}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    under_test = ProbeUnderTest(
        probe=PropsVisionProbe("http://llama:8080/", client),
        set_vision=lambda seeing: world.update(vision=seeing),
        break_world=lambda: world.update(broken=True),
    )
    return under_test, client


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.parametrize("build", [_scripted, _props], ids=["scripted", "props"])
async def test_the_contract_holds(check: Check, build: Build) -> None:
    under_test, client = build()
    try:
        await check(under_test)
    finally:
        if client is not None:
            await client.aclose()
