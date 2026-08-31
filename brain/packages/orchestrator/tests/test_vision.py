"""The vision probe (ADR-0029): what a live /props says, and what CORTEX_VISION builds.

The probe exists because a brain-side declaration can disagree with the running server, and
both directions of that disagreement are bad: advertising vision the server lacks spends the
whole privacy cost of a screen read on an image nothing can read, and hiding vision the server
has silently removes the capability.

The port's own promises are asserted in `test_vision_probe_contract.py`, over this adapter and
the core fake alike. What is left here is this adapter's reading of one particular server's
JSON, and what `build_vision` hands the composition root for each mode.
"""

import httpx
import pytest

from cortex_core import CaptureBounds, InMemoryBodyGateway
from cortex_orchestrator.config import InferenceConfig
from cortex_orchestrator.config_body import BodyConfig
from cortex_orchestrator.vision import PROBE_TIMEOUT_S, PropsVisionProbe, build_vision


def _client(handler: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))  # pyright: ignore[reportArgumentType]


async def test_a_server_reporting_vision_is_believed() -> None:
    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return httpx.Response(
            200, json={"modalities": {"vision": True, "audio": True}, "model_path": "/m.gguf"}
        )

    async with _client(handler) as client:
        assert await PropsVisionProbe("http://llama:8080", client).can_see() is True
    assert asked == ["http://llama:8080/props"]


async def test_a_text_only_server_reports_no_vision() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"modalities": {"vision": False}})

    async with _client(handler) as client:
        assert await PropsVisionProbe("http://llama:8080", client).can_see() is False


async def test_a_trailing_slash_on_the_endpoint_does_not_double_up() -> None:
    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return httpx.Response(200, json={"modalities": {"vision": True}})

    async with _client(handler) as client:
        assert await PropsVisionProbe("http://llama:8080/", client).can_see() is True
    assert asked == ["http://llama:8080/props"]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"modalities": None},
        {"modalities": []},
        {"modalities": {"vision": "yes"}},
        [1, 2, 3],
    ],
)
async def test_any_other_props_shape_counts_as_no_vision(body: object) -> None:
    # A live server's JSON is that server's to change between versions; a strict read would
    # lose vision on an upgrade, and a lenient one only ever fails closed.
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with _client(handler) as client:
        assert await PropsVisionProbe("http://llama:8080", client).can_see() is False


async def test_a_non_2xx_props_counts_as_no_vision() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    async with _client(handler) as client:
        assert await PropsVisionProbe("http://llama:8080", client).can_see() is False


async def test_a_props_body_that_is_not_json_counts_as_no_vision() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>oops</html>")

    async with _client(handler) as client:
        assert await PropsVisionProbe("http://llama:8080", client).can_see() is False


def _configs(monkeypatch: pytest.MonkeyPatch, mode: str) -> tuple[InferenceConfig, BodyConfig]:
    """The two env-read settings objects the composition root hands `build_vision`."""
    monkeypatch.setenv("CORTEX_VISION", mode)
    monkeypatch.setenv("CORTEX_INFERENCE_ENDPOINT", "http://llama:8080")
    monkeypatch.setenv("CORTEX_BODY_CAPTURE_MAX_EDGE", "1280")
    monkeypatch.setenv("CORTEX_BODY_MAX_IMAGE_BYTES", "4000000")
    return InferenceConfig(), BodyConfig()


async def test_auto_builds_a_live_probe_over_the_configured_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In `auto` mode the builder returns capture bounds for the tool and a live probe the
    registry asks again on every call."""
    inference, body_config = _configs(monkeypatch, "auto")
    bounds, probe, close = build_vision(inference, body_config, InMemoryBodyGateway())

    assert bounds == CaptureBounds(max_edge=1280, max_bytes=4_000_000)
    assert isinstance(probe, PropsVisionProbe)
    # Nothing listens at that endpoint, so the probe answers False over a real HTTP client.
    assert await probe.can_see() is False
    await close()


async def test_on_fixes_the_answer_without_a_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """In `on` mode the tool is registered with no probe, so no server is consulted."""
    inference, body_config = _configs(monkeypatch, "on")
    bounds, probe, close = build_vision(inference, body_config, InMemoryBodyGateway())

    assert bounds == CaptureBounds(max_edge=1280, max_bytes=4_000_000)
    assert probe is None
    await close()


async def test_off_registers_no_capture_tool_at_all(monkeypatch: pytest.MonkeyPatch) -> None:
    inference, body_config = _configs(monkeypatch, "off")
    bounds, probe, close = build_vision(inference, body_config, InMemoryBodyGateway())

    assert (bounds, probe) == (None, None)
    await close()


async def test_without_a_body_there_is_nothing_to_probe_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a body gateway there is no capture to take, so the builder returns neither bounds
    nor a probe."""
    inference, body_config = _configs(monkeypatch, "auto")
    bounds, probe, close = build_vision(inference, body_config, None)

    assert (bounds, probe) == (None, None)
    await close()


def test_the_probes_leash_is_short_enough_to_sit_inside_a_turn() -> None:
    """The probe runs once per advertisement and once per call, so its timeout has to be short
    enough not to hold a turn open.

    Measured on the real stack 2026-08-06: /props answers in 1.5 ms idle and 1.7 ms with a
    generation in flight, worst of 40 samples 2.5 ms.
    """
    assert 0 < PROBE_TIMEOUT_S <= 2.0
