"""The real adapter's own half: URL shape, and every failure collapsed into ``ModelHostError``.

The behaviour a ``ModelHost`` owes is pinned by the shared contract suite, which drives this
adapter against a real supervisor. What is left here is the wire mapping the contract cannot
reach: a sidecar that answers nonsense, refuses, or is not there at all. Same split as the
handoff store's contract suite plus its adapter-only error tests.

Only ``ModelHostError`` may cross the port: ``residency_moves`` catches exactly that, and anything
else (an ``httpx`` error, a ``ValueError``, a ``KeyError``) would escape as an untyped crash and
fail the turn instead of failing the swap.

Distrust-green proofs, measured across ``packages/model_manager`` one mutation at a time:

- letting ``httpx.HTTPError`` propagate instead of wrapping it reddens exactly 1,
  ``test_a_sidecar_that_is_not_there_is_a_typed_model_host_error``;
- accepting any status code (dropping the non-200 branch) reddens 3, the whole parameterization of
  ``test_a_refusal_carries_its_code_and_the_sidecars_reason``;
- defaulting an unknown state word to ``LOADING`` instead of raising reddens 3, the whole
  parameterization of ``test_a_state_word_this_version_does_not_know_is_a_failure_not_a_guess``;
- reporting READY whatever the sidecar said reddens 11, of which 4 are here and 7 are the shared
  contract suite's supervisor cases.
"""

import logging
from http import HTTPStatus

import httpx
import pytest

from cortex_core import ModelHostError, ModelHostState
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
    """The wire the runbook documents and the sidecar routes, asserted as the requests sent."""
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
    """An id is a name, not a path fragment: a slash in one must not reroute the request."""
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
    """The sidecar's exit code is the only diagnosis the brain side ever sees, so it is logged."""
    host = _host(_answer("failed", "the process exited with code 1"))
    assert await host.status("brain") is ModelHostState.FAILED
    record = caplog.records[-1]
    assert (record.levelno, record.message) == (logging.ERROR, "a hosted model process has failed")
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
    """A 404 and a 503 both abort the swap, but the message has to say which and why."""

    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(code, json={"error": "unknown model 'brain'"})

    with pytest.raises(ModelHostError, match=f"HTTP {code.value}") as excinfo:
        await _host(httpx.MockTransport(handle)).start("brain")
    assert "unknown model" in str(excinfo.value)


@pytest.mark.parametrize("payload", [b"not json at all", b"[1, 2, 3]"])
async def test_a_body_that_is_not_an_object_is_a_failure_not_a_default(payload: bytes) -> None:
    """A sidecar answering the wrong shape must fail the swap, never decode into a state."""

    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(HTTPStatus.OK, content=payload)

    with pytest.raises(ModelHostError, match="model host answered"):
        await _host(httpx.MockTransport(handle)).status("brain")


@pytest.mark.parametrize("state", ["swapping", "", None])
async def test_a_state_word_this_version_does_not_know_is_a_failure_not_a_guess(
    state: str | None,
) -> None:
    """Guessing would let a newer sidecar's state be read as the wrong one; the swap fails safe."""

    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(HTTPStatus.OK, json={"state": state})

    with pytest.raises(ModelHostError, match="which is not known"):
        await _host(httpx.MockTransport(handle)).status("brain")
