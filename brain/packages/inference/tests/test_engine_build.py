import json
import logging
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
import pytest

from cortex_core import (
    DecodeCadence,
    DecodeStop,
    Message,
    ModelLease,
    Role,
    SingleResidentModelManager,
    StopReason,
    TextChunk,
)
from cortex_inference import LlamaCppBackend

_BACKEND_LOGGER = "cortex_inference.backend"
_SERVED_BY = "model now served by engine build"
_ENDPOINT = "http://llama-cortex:8080"
_AT = datetime(2026, 9, 24, 3, 0, 0, tzinfo=UTC)

_Handler = Callable[[httpx.Request], httpx.Response]


class _PerModelServers:
    def __init__(self, endpoints: dict[str, str]) -> None:
        self._endpoints = endpoints

    @asynccontextmanager
    async def acquire(self, model: str) -> AsyncGenerator[ModelLease]:
        yield ModelLease(endpoint=self._endpoints[model])


def _messages() -> list[Message]:
    return [Message(role=Role.USER, text="hello", at=_AT, turn_id="t-1")]


def _completion(fingerprint: object) -> bytes:
    chunks: list[dict[str, object]] = [
        {"choices": [{"delta": {"content": "hi"}}], "system_fingerprint": fingerprint},
        {
            "choices": [{"finish_reason": "stop", "index": 0, "delta": {}}],
            "system_fingerprint": fingerprint,
            "timings": {"predicted_per_second": 40.0, "predicted_n": 3},
        },
    ]
    return (
        "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks).encode() + b"data: [DONE]\n\n"
    )


def _serving(*bodies: bytes) -> _Handler:
    queue = list(bodies)
    return lambda _request: httpx.Response(200, content=queue.pop(0))


def _backend(handler: _Handler) -> LlamaCppBackend:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LlamaCppBackend(SingleResidentModelManager("cortex", _ENDPOINT), client)


async def _run(backend: LlamaCppBackend, model: str = "cortex") -> list[object]:
    return [event async for event in backend.stream(model, _messages())]


def _served(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == _BACKEND_LOGGER and r.msg == _SERVED_BY]


async def test_the_first_completion_names_its_build_once(caplog: pytest.LogCaptureFixture) -> None:
    backend = _backend(_serving(_completion("b10680-d7bd3bfca"), _completion("b10680-d7bd3bfca")))
    with caplog.at_level(logging.INFO, logger=_BACKEND_LOGGER):
        await _run(backend)
        await _run(backend)
    [record] = _served(caplog)
    assert record.levelno == logging.INFO
    assert getattr(record, "model", None) == "cortex"
    assert getattr(record, "endpoint", None) == _ENDPOINT
    assert getattr(record, "build", None) == "b10680-d7bd3bfca"


async def test_a_changed_build_is_named_again_each_time_it_changes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    backend = _backend(
        _serving(_completion("b1-aaa"), _completion("b2-bbb"), _completion("b1-aaa"))
    )
    with caplog.at_level(logging.INFO, logger=_BACKEND_LOGGER):
        for _ in range(3):
            await _run(backend)
    assert [getattr(r, "build", None) for r in _served(caplog)] == ["b1-aaa", "b2-bbb", "b1-aaa"]


async def test_each_model_names_its_own_build(caplog: pytest.LogCaptureFixture) -> None:
    endpoints = {"cortex": "http://cortex:8080", "deep": "http://deep:8081"}
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(_serving(*[_completion("b1-aaa")] * 3))
    )
    backend = LlamaCppBackend(_PerModelServers(endpoints), client)
    with caplog.at_level(logging.INFO, logger=_BACKEND_LOGGER):
        await _run(backend, "cortex")
        await _run(backend, "deep")
        await _run(backend, "cortex")
    named = [(getattr(r, "model", None), getattr(r, "endpoint", None)) for r in _served(caplog)]
    assert named == [("cortex", "http://cortex:8080"), ("deep", "http://deep:8081")]


@pytest.mark.parametrize("fingerprint", [None, "", 10680, ["b1-aaa"]])
async def test_a_chunk_naming_no_usable_build_logs_nothing_and_keeps_the_reply(
    caplog: pytest.LogCaptureFixture, fingerprint: object
) -> None:
    with caplog.at_level(logging.INFO, logger=_BACKEND_LOGGER):
        events = await _run(_backend(_serving(_completion(fingerprint))))
    assert _served(caplog) == []
    assert events == [
        TextChunk("hi"),
        DecodeStop(StopReason.FINISHED),
        DecodeCadence(tokens_per_second=40.0, tokens=3),
    ]


async def test_a_choiceless_chunk_still_names_its_build(caplog: pytest.LogCaptureFixture) -> None:
    body = b'data: {"choices": [], "system_fingerprint": "b1-aaa"}\n\ndata: [DONE]\n\n'
    with caplog.at_level(logging.INFO, logger=_BACKEND_LOGGER):
        events = await _run(_backend(_serving(body)))
    assert events == []
    assert [getattr(r, "build", None) for r in _served(caplog)] == ["b1-aaa"]
