"""The capability read behind the per-request trace budget (ADR-0005 request-lever addendum).

Four worlds over ``httpx.MockTransport``, so the whole probe runs with no GPU and no network. The
bodies are the ones two real llama.cpp builds returned, measured 2026-08-29 by the agent against
one model in one minute: ``b10666-4e97ac86e`` rejects an out-of-range budget by name and
``b9870-2d973636e`` answers the completion, having never heard of the field.

What the probe must not do is answer yes on anything softer than that rejection, since a yes puts
a key on every later request and an engine that ignores it says nothing at all. So the two near
misses are checks of their own: a 400 for some other reason, and a completion that came back fine.
"""

import json
from collections.abc import Callable

import httpx
import pytest

from cortex_inference.lever import reads_a_trace_budget
from cortex_inference.request import TRACE_BUDGET_KEY

pytestmark = pytest.mark.asyncio

_ENDPOINT = "http://llama-cortex:8080"

# What b10666-4e97ac86e really answered, quoted from the run in the ADR addendum's table.
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
# A 400 that is about something else entirely, which must not be read as a yes.
_OTHER_REFUSAL = {"error": {"code": 400, "message": "Illegal param: max_tokens", "type": "x"}}
# The shape a build with no opinion about the field returns: the completion it was asked for.
_COMPLETION = {"choices": [{"finish_reason": "length", "message": {"content": "."}}]}


_Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: _Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_a_build_that_range_checks_the_field_reads_a_trace_budget() -> None:
    """The yes: a 400 naming the key is a build that parsed it.

    The request is asserted beside the verdict, because a probe that asked the wrong question
    would answer confidently and wrongly: the value has to be outside the range a knowing build
    accepts, or every build answers 200 and the lever is never found.
    """
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
    """The no that matters: the field was ignored, so the request must never carry one.

    This is every llama.cpp older than the build that introduced the key, and it is the case the
    floor exists for. Ignoring is silent, so nothing but this probe distinguishes it from a build
    that honoured a budget the model then had no reason to spend.
    """

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_COMPLETION)

    async with _client(handler) as client:
        assert await reads_a_trace_budget(_ENDPOINT, "cortex", client) is False


async def test_a_refusal_about_something_else_is_not_a_yes() -> None:
    """A 400 that does not name the field says nothing about the field."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=_OTHER_REFUSAL)

    async with _client(handler) as client:
        assert await reads_a_trace_budget(_ENDPOINT, "cortex", client) is False


async def test_a_server_that_cannot_be_reached_is_read_as_no_lever() -> None:
    """Every failure is a no, and the request goes back to what it always was.

    The direction is the design. A wrong no costs a deployment a knob it can set by hand
    (``CORTEX_INFERENCE_TRACE_LEVER=on``); a wrong yes puts a key on every request that nothing
    enforces and says so nowhere.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        msg = "no route to host"
        raise httpx.ConnectError(msg, request=request)

    async with _client(handler) as client:
        assert await reads_a_trace_budget(_ENDPOINT, "cortex", client) is False
