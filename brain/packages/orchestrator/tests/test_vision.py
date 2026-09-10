import logging

import httpx
import pytest

from cortex_core import CaptureBounds, InMemoryBodyGateway, record_fields
from cortex_orchestrator.config import InferenceConfig
from cortex_orchestrator.config_body import BodyConfig
from cortex_orchestrator.vision import PROBE_TIMEOUT_S, PropsVisionProbe, build_vision

_LOGGER = "cortex_orchestrator.vision"


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
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with _client(handler) as client:
        assert await PropsVisionProbe("http://llama:8080", client).can_see() is False


async def test_the_answered_line_names_the_engine_that_answered_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"modalities": {"vision": True}, "build_info": "b10680-d7bd3bfca"}
        )

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        async with _client(handler) as client:
            assert await PropsVisionProbe("http://llama:8080", client).can_see() is True
    (record,) = caplog.records
    assert record_fields(record) == {
        "endpoint": "http://llama:8080/props",
        "vision": True,
        "build": "b10680-d7bd3bfca",
    }


@pytest.mark.parametrize("body", [{"modalities": {"vision": True}}, {"build_info": 10680}, "b1068"])
async def test_a_server_naming_no_build_still_gets_its_verdict_read(
    body: object, caplog: pytest.LogCaptureFixture
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        async with _client(handler) as client:
            await PropsVisionProbe("http://llama:8080", client).can_see()
    (record,) = caplog.records
    assert record_fields(record)["build"] is None


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
    inference, body_config = _configs(monkeypatch, "auto")
    bounds, probe, close = build_vision(inference, body_config, InMemoryBodyGateway())

    assert bounds == CaptureBounds(max_edge=1280, max_bytes=4_000_000)
    assert isinstance(probe, PropsVisionProbe)
    assert await probe.can_see() is False
    await close()


async def test_on_fixes_the_answer_without_a_probe(monkeypatch: pytest.MonkeyPatch) -> None:
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
    inference, body_config = _configs(monkeypatch, "auto")
    bounds, probe, close = build_vision(inference, body_config, None)

    assert (bounds, probe) == (None, None)
    await close()


def test_the_probes_leash_is_short_enough_to_sit_inside_a_turn() -> None:
    assert 0 < PROBE_TIMEOUT_S <= 2.0
