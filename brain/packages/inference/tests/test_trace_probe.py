import json
import logging
from collections.abc import Callable, Sequence

import httpx
import pytest

from cortex_inference.request import TRACE_BUDGET_KEY
from cortex_inference.trace_probe import (
    TraceBudgetProbe,
    TraceProbeUnansweredError,
    reads_a_trace_budget,
)

pytestmark = pytest.mark.asyncio

_ENDPOINT = "http://llama-cortex:8080"

# What build b10666-4e97ac86e answered, as docs/readings/thinking-switch.md records the run.
_REJECTION = {
    "error": {
        "code": 400,
        "message": (
            f"Field '{TRACE_BUDGET_KEY}': Value must be between -1 <= value <= 2147483647, "
            "but got -2"
        ),
        "type": "invalid_request_error",
    }
}
_OTHER_REFUSAL = {"error": {"code": 400, "message": "Illegal param: max_tokens", "type": "x"}}
_COMPLETION = {"choices": [{"finish_reason": "length", "message": {"content": "."}}]}


_Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: _Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_a_build_that_range_checks_the_field_reads_a_trace_budget() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["url"] = str(request.url)
        return httpx.Response(400, json=_REJECTION)

    async with _client(handler) as client:
        assert await reads_a_trace_budget(_ENDPOINT, "cortex", client) is True
    body = captured["body"]
    assert isinstance(body, dict)
    assert body[TRACE_BUDGET_KEY] == -2
    assert body["max_tokens"] == 1
    assert captured["url"] == f"{_ENDPOINT}/v1/chat/completions"


async def test_a_build_that_answers_the_completion_reads_no_trace_budget() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_COMPLETION)

    async with _client(handler) as client:
        assert await reads_a_trace_budget(_ENDPOINT, "cortex", client) is False


async def test_a_refusal_about_something_else_is_not_a_yes() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=_OTHER_REFUSAL)

    async with _client(handler) as client:
        assert await reads_a_trace_budget(_ENDPOINT, "cortex", client) is False


async def test_a_server_that_cannot_be_reached_gives_no_answer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        msg = "no route to host"
        raise httpx.ConnectError(msg, request=request)

    async with _client(handler) as client:
        with pytest.raises(TraceProbeUnansweredError, match="no route to host"):
            await reads_a_trace_budget(_ENDPOINT, "cortex", client)


async def test_a_server_still_loading_its_model_gives_no_answer() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json=_LOADING)

    async with _client(handler) as client:
        with pytest.raises(TraceProbeUnansweredError, match="answered 503"):
            await reads_a_trace_budget(_ENDPOINT, "cortex", client)


_LOADING = {"error": {"code": 503, "message": "Loading model", "type": "unavailable_error"}}
_LOGGER = "cortex_inference.trace_probe"


def _down_then(answers: Sequence[httpx.Response]) -> tuple[_Handler, list[int]]:
    """Down for the first ask, then ``answers`` in turn, the last one repeated."""
    asked: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(len(asked))
        if len(asked) == 1:
            msg = "Name or service not known"
            raise httpx.ConnectError(msg, request=request)
        return answers[min(len(asked) - 2, len(answers) - 1)]

    return handler, asked


async def test_a_probe_with_no_answer_asks_again_until_the_engine_answers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    handler, asked = _down_then(
        [httpx.Response(503, json=_LOADING), httpx.Response(400, json=_REJECTION)]
    )
    async with _client(handler) as client:
        probe = TraceBudgetProbe(_ENDPOINT, "cortex", client)
        with caplog.at_level(logging.INFO, logger=_LOGGER):
            seen = [await probe.reads() for _ in range(4)]
    assert seen == [None, None, True, True]
    assert len(asked) == 3
    records = [(r.levelno, r.getMessage()) for r in caplog.records if r.name == _LOGGER]
    assert records == [
        (logging.WARNING, "trace budget probe failed; asking again before the next request"),
        (logging.INFO, "trace budget probe answered"),
    ]
    answered = [r for r in caplog.records if r.name == _LOGGER][-1]
    assert getattr(answered, "reads_budget", None) is True
    assert getattr(answered, "endpoint", None) == f"{_ENDPOINT}/v1/chat/completions"


async def test_a_no_from_a_serving_engine_is_settled_and_not_asked_again() -> None:
    handler, asked = _down_then([httpx.Response(200, json=_COMPLETION)])
    async with _client(handler) as client:
        probe = TraceBudgetProbe(_ENDPOINT, "cortex", client)
        seen = [await probe.reads() for _ in range(3)]
    assert seen == [None, False, False]
    assert len(asked) == 2
