import json
from collections.abc import Callable

import httpx
import pytest
from template_servers import TEMPLATE_REFUSAL, leading_systems, turn_per_system

from cortex_inference.system_probe import SystemProbeError, delivers_system_messages

_ENDPOINT = "http://model-host:8081"

_Handler = Callable[[httpx.Request], httpx.Response]


def _answering(response: httpx.Response) -> _Handler:
    def handler(_request: httpx.Request) -> httpx.Response:
        return response

    return handler


def _rendering(render: Callable[[list[str]], str]) -> _Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"prompt": render(leading_systems(json.loads(request.content)))}
        )

    return handler


async def _ask(handler: _Handler, count: int = 3) -> bool:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await delivers_system_messages(_ENDPOINT, "brain", count, client)


def _merged_in_one_turn(systems: list[str]) -> str:
    return "<|im_start|>system\n" + "\n".join(systems) + "<|im_end|>\n<|im_start|>user\n."


def _first_two_merged(systems: list[str]) -> str:
    return _merged_in_one_turn(systems[:2])


def _reversed_turns(systems: list[str]) -> str:
    return turn_per_system(systems[::-1])


async def test_the_probe_asks_the_template_to_render_marked_system_messages_and_nothing_else() -> (
    None
):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _rendering(turn_per_system)(request)

    assert await _ask(handler, 3) is True
    (request,) = seen
    assert str(request.url) == f"{_ENDPOINT}/apply-template"
    body = json.loads(request.content)
    assert set(body) == {"model", "messages"}
    assert body["model"] == "brain"
    roles = [message["role"] for message in body["messages"]]
    assert roles == ["system", "system", "system", "user"]
    markers = leading_systems(body)
    assert len(set(markers)) == 3
    assert all(a not in b for a in markers for b in markers if a != b)
    assert body["messages"][-1]["content"] == "."
    assert request.extensions["timeout"] == {"connect": 2.0, "read": 2.0, "write": 2.0, "pool": 2.0}


async def test_a_trailing_slash_on_the_endpoint_is_not_doubled() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _rendering(turn_per_system)(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await delivers_system_messages(f"{_ENDPOINT}/", "brain", 2, client)
    assert seen == [f"{_ENDPOINT}/apply-template"]


@pytest.mark.parametrize("count", [2, 3])
async def test_a_template_with_a_turn_per_system_message_delivers(count: int) -> None:
    assert await _ask(_rendering(turn_per_system), count) is True


@pytest.mark.parametrize("count", [2, 3])
async def test_a_template_that_merges_every_system_message_itself_delivers(count: int) -> None:
    assert await _ask(_rendering(_merged_in_one_turn), count) is True


async def test_a_template_that_drops_the_third_system_message_does_not_deliver() -> None:
    assert await _ask(_rendering(_first_two_merged), 3) is False
    assert await _ask(_rendering(_first_two_merged), 2) is True


async def test_a_template_that_renders_the_system_messages_out_of_order_does_not_deliver() -> None:
    assert await _ask(_rendering(_reversed_turns), 3) is False


async def test_a_template_that_raises_does_not_deliver() -> None:
    assert await _ask(_answering(httpx.Response(500, json=TEMPLATE_REFUSAL))) is False


def _raising(error: httpx.HTTPError) -> _Handler:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise error

    return handler


@pytest.mark.parametrize(
    ("handler", "reason"),
    [
        (_answering(httpx.Response(404, text="Not Found")), "answered HTTP 404"),
        (_raising(httpx.ReadTimeout("timed out")), "ReadTimeout: timed out"),
        (_raising(httpx.ConnectError("no route to host")), "ConnectError: no route to host"),
        (_answering(httpx.Response(200, text="<html>")), "not JSON"),
        (_answering(httpx.Response(200, json={"text": "x"})), "no prompt string"),
        (_answering(httpx.Response(200, json={"prompt": 7})), "no prompt string"),
        (_answering(httpx.Response(200, json=["prompt"])), "no prompt string"),
    ],
)
async def test_an_answer_the_probe_cannot_read_is_a_failure_and_not_a_no(
    handler: _Handler, reason: str
) -> None:
    with pytest.raises(SystemProbeError, match=reason):
        await _ask(handler)
