import json
from collections.abc import Callable

import httpx
import pytest

from cortex_inference.request import TRACE_BUDGET_KEY
from cortex_inference.trace_probe import reads_a_trace_budget

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


async def test_a_server_that_cannot_be_reached_is_read_as_not_reading_the_budget() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        msg = "no route to host"
        raise httpx.ConnectError(msg, request=request)

    async with _client(handler) as client:
        assert await reads_a_trace_budget(_ENDPOINT, "cortex", client) is False
