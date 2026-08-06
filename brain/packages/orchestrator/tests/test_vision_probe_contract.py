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
