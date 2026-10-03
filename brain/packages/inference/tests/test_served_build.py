import re

import httpx
import pytest
from served_build import served_build

_ENDPOINT = "http://llama:8081/"


def _client(handler: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))  # pyright: ignore[reportArgumentType]


async def test_the_build_on_props_is_returned_and_printed_under_its_role(
    capsys: pytest.CaptureFixture[str],
) -> None:
    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return httpx.Response(200, json={"build_info": "b10680-d7bd3bfca", "model_path": "/e.gguf"})

    async with _client(handler) as client:
        assert await served_build(client, _ENDPOINT, "cortex") == "b10680-d7bd3bfca"
    assert asked == ["http://llama:8081/props"]
    assert capsys.readouterr().out == f"\ncortex  b10680-d7bd3bfca at {_ENDPOINT}\n"


@pytest.mark.parametrize("body", [{}, {"build_info": 10680}])
async def test_props_without_a_named_build_fails_the_run_before_it_measures(
    body: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with _client(handler) as client:
        with pytest.raises(
            AssertionError, match=re.escape(f"GET /props at {_ENDPOINT} names no build_info")
        ):
            await served_build(client, _ENDPOINT, "embedder")
    assert capsys.readouterr().out == ""


async def test_a_props_error_fails_the_run_rather_than_printing_no_build() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with _client(handler) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await served_build(client, _ENDPOINT, "embedder")
