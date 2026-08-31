import logging
from http import HTTPStatus

import httpx
import pytest

from cortex_core import (
    ControlBounds,
    DeviceMemory,
    ModelHostError,
    ModelHostState,
    ModelNotHostedError,
    PlainFormatter,
)
from cortex_model_manager import HttpModelHost

_ENDPOINT = "http://model-host:9300"


def _host(handler: httpx.MockTransport) -> HttpModelHost:
    return HttpModelHost(f"{_ENDPOINT}/", httpx.AsyncClient(transport=handler))


def _answer(state: str, detail: str = "") -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            HTTPStatus.OK,
            json={"model": request.url.path.split("/")[2], "state": state, "detail": detail},
        )

    return httpx.MockTransport(handle)


async def test_the_three_verbs_hit_the_documented_method_and_path() -> None:
    seen: list[tuple[str, str]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        return httpx.Response(HTTPStatus.OK, json={"state": "ready", "detail": ""})

    host = _host(httpx.MockTransport(handle))
    await host.start("brain")
    await host.stop("brain")
    assert await host.status("brain") is ModelHostState.READY
    assert seen == [
        ("POST", "/models/brain/start"),
        ("POST", "/models/brain/stop"),
        ("GET", "/models/brain"),
    ]


async def test_a_logical_id_is_escaped_rather_than_pasted_into_the_path() -> None:
    seen: list[bytes] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.raw_path)
        return httpx.Response(HTTPStatus.OK, json={"state": "stopped", "detail": ""})

    await _host(httpx.MockTransport(handle)).status("odd/id")
    assert seen == [b"/models/odd%2Fid"]


@pytest.mark.parametrize("state", list(ModelHostState))
async def test_every_state_the_port_defines_round_trips_off_the_wire(state: ModelHostState) -> None:
    assert await _host(_answer(state.value)).status("brain") is state


async def test_a_failed_state_is_a_normal_answer_and_is_logged_with_its_detail(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = _host(_answer("failed", "the process exited with code 1"))
    assert await host.status("brain") is ModelHostState.FAILED
    record = caplog.records[-1]
    assert record.levelno == logging.ERROR
    assert PlainFormatter().format(record) == (
        "ERROR:cortex_model_manager.adapter:a hosted model process has failed "
        'detail="the process exited with code 1" model=brain'
    )
    assert record.__dict__["detail"] == "the process exited with code 1"


async def test_a_sidecar_that_is_not_there_is_a_typed_model_host_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        msg = "connection refused"
        raise httpx.ConnectError(msg, request=request)

    with pytest.raises(ModelHostError, match="did not answer for model 'brain'") as excinfo:
        await _host(httpx.MockTransport(handle)).status("brain")
    assert isinstance(excinfo.value.__cause__, httpx.ConnectError)


@pytest.mark.parametrize(
    "code", [HTTPStatus.NOT_FOUND, HTTPStatus.SERVICE_UNAVAILABLE, HTTPStatus.INTERNAL_SERVER_ERROR]
)
async def test_a_refusal_carries_its_code_and_the_sidecars_reason(code: HTTPStatus) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(code, json={"error": "unknown model 'brain'"})

    with pytest.raises(ModelHostError, match=f"HTTP {code.value}") as excinfo:
        await _host(httpx.MockTransport(handle)).start("brain")
    assert "unknown model" in str(excinfo.value)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (HTTPStatus.NOT_FOUND, ModelNotHostedError),
        (HTTPStatus.SERVICE_UNAVAILABLE, ModelHostError),
        (HTTPStatus.INTERNAL_SERVER_ERROR, ModelHostError),
    ],
)
async def test_only_a_404_about_a_tier_says_the_host_does_not_serve_it(
    code: HTTPStatus, expected: type[ModelHostError]
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(code, json={"error": "something the sidecar said"})

    with pytest.raises(ModelHostError) as excinfo:
        await _host(httpx.MockTransport(handle)).status("brain")
    assert type(excinfo.value) is expected


async def test_a_404_that_is_not_about_a_tier_is_a_wrong_endpoint_not_a_missing_model() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(HTTPStatus.NOT_FOUND, text="not found")

    host = _host(httpx.MockTransport(handle))
    for read in (host.device_memory, host.control_bounds, host.boot_id):
        with pytest.raises(ModelHostError) as excinfo:
            await read()
        assert not isinstance(excinfo.value, ModelNotHostedError)


@pytest.mark.parametrize("payload", [b"not json at all", b"[1, 2, 3]"])
async def test_a_body_that_is_not_an_object_is_a_failure_not_a_default(payload: bytes) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(HTTPStatus.OK, content=payload)

    with pytest.raises(ModelHostError, match="model host answered"):
        await _host(httpx.MockTransport(handle)).status("brain")


@pytest.mark.parametrize("state", ["swapping", "", None])
async def test_a_state_word_this_version_does_not_know_is_a_failure_not_a_guess(
    state: str | None,
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(HTTPStatus.OK, json={"state": state})

    with pytest.raises(ModelHostError, match="which is not known"):
        await _host(httpx.MockTransport(handle)).status("brain")


def _health(body: dict[str, object]) -> httpx.MockTransport:
    """A sidecar whose ``/health`` answers ``body`` and whose other routes are never asked."""

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(HTTPStatus.OK, json=body)

    return httpx.MockTransport(handle)


async def test_the_card_is_read_off_the_health_route_and_nowhere_else() -> None:
    seen: list[tuple[str, str]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        return httpx.Response(
            HTTPStatus.OK,
            json={"status": "ok", "device_free_mib": 22484, "device_total_mib": 24463},
        )

    memory = await _host(httpx.MockTransport(handle)).device_memory()
    assert memory == DeviceMemory(free_mib=22484, total_mib=24463)
    assert seen == [("GET", "/health")]


@pytest.mark.parametrize(
    "body",
    [
        {"status": "ok", "device_free_mib": None, "device_total_mib": None},
        {"status": "ok"},
        {"status": "ok", "device_total_mib": 24463},
        {"status": "ok", "device_free_mib": "plenty", "device_total_mib": 24463},
    ],
)
async def test_a_health_body_without_two_figures_is_no_reading(body: dict[str, object]) -> None:
    assert await _host(_health(body)).device_memory() is None


async def test_the_control_bounds_are_read_off_the_same_health_route() -> None:
    seen: list[tuple[str, str]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        return httpx.Response(
            HTTPStatus.OK,
            json={
                "status": "ok",
                "probe_timeout_s": 5.0,
                "stop_grace_s": 10.0,
                "reap_timeout_s": 30.0,
            },
        )

    bounds = await _host(httpx.MockTransport(handle)).control_bounds()
    assert bounds == ControlBounds(probe_timeout_s=5.0, stop_grace_s=10.0, reap_timeout_s=30.0)
    assert seen == [("GET", "/health")]


@pytest.mark.parametrize(
    "body",
    [
        {"status": "ok", "stop_grace_s": 10.0, "reap_timeout_s": 30.0},
        {"status": "ok"},
        {
            "status": "ok",
            "probe_timeout_s": "five",
            "stop_grace_s": 10.0,
            "reap_timeout_s": 30.0,
        },
        {
            "status": "ok",
            "probe_timeout_s": 5.0,
            "stop_grace_s": -10.0,
            "reap_timeout_s": 30.0,
        },
        {
            "status": "ok",
            "probe_timeout_s": 5.0,
            "stop_grace_s": 10.0,
            "reap_timeout_s": True,
        },
    ],
)
async def test_a_health_body_without_all_three_bounds_is_no_bounds(body: dict[str, object]) -> None:
    assert await _host(_health(body)).control_bounds() is None


async def test_the_answering_daemon_is_named_off_the_same_health_route() -> None:
    seen: list[tuple[str, str]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        return httpx.Response(
            HTTPStatus.OK, json={"status": "ok", "boot_id": "0f9c1d2e3a4b5c6d7e8f9a0b1c2d3e4f"}
        )

    assert await _host(httpx.MockTransport(handle)).boot_id() == "0f9c1d2e3a4b5c6d7e8f9a0b1c2d3e4f"
    assert seen == [("GET", "/health")]


@pytest.mark.parametrize(
    "body",
    [
        {"status": "ok"},
        {"status": "ok", "boot_id": None},
        {"status": "ok", "boot_id": ""},
        {"status": "ok", "boot_id": 1},
    ],
)
async def test_a_health_body_that_names_no_boot_is_no_answer(body: dict[str, object]) -> None:
    assert await _host(_health(body)).boot_id() is None


async def test_a_sidecar_that_cannot_be_asked_which_daemon_it_is_is_a_typed_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(HTTPStatus.SERVICE_UNAVAILABLE, text="the supervisor is wedged")

    with pytest.raises(ModelHostError, match="for which daemon is answering"):
        await _host(httpx.MockTransport(handle)).boot_id()


async def test_a_sidecar_that_cannot_answer_about_its_bounds_is_a_typed_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(HTTPStatus.SERVICE_UNAVAILABLE, text="the supervisor is wedged")

    with pytest.raises(ModelHostError, match="for the bounds of its own control calls"):
        await _host(httpx.MockTransport(handle)).control_bounds()


async def test_a_sidecar_that_cannot_answer_about_the_card_is_a_typed_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(HTTPStatus.SERVICE_UNAVAILABLE, text="the supervisor is wedged")

    with pytest.raises(ModelHostError, match="for the device it runs on"):
        await _host(httpx.MockTransport(handle)).device_memory()
