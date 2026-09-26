import json
from collections.abc import Callable
from functools import partial

import httpx
import pytest
from stream_contract import (
    CONTRACT_ASIDE,
    CONTRACT_CALL,
    CONTRACT_MODEL,
    CONTRACT_REPLY,
    CONTRACT_THINKING,
    STREAM_CHECKS,
    BackendUnderTest,
    StreamCheck,
    events_of,
)
from template_servers import TemplateServer

from cortex_core import (
    DecodeCadence,
    DecodeStop,
    InferenceError,
    InferenceEvent,
    ReasoningChunk,
    ScriptedInferenceBackend,
    SingleResidentModelManager,
    StopReason,
    TextChunk,
    ToolCall,
)
from cortex_inference import LlamaCppBackend

_ENDPOINT = "http://model-host:8080"

_TPS = 24.61
_TOKENS = 12

_THOUGHTS = ("let me ", "check")
_WORDS = ("The ", "answer ", "is here")

_ARGUMENT_FRAGMENTS = ('{"path"', ':"/x"}')


def _sse(*chunks: str) -> bytes:
    return "".join(f"data: {chunk}\n\n" for chunk in chunks).encode()


def _deliberating_body() -> bytes:
    return _sse(
        json.dumps({"choices": [{"delta": {"role": "assistant"}, "finish_reason": None}]}),
        json.dumps({"choices": [{"delta": {"reasoning_content": _THOUGHTS[0]}}]}),
        json.dumps(
            {"choices": [{"delta": {"reasoning_content": _THOUGHTS[1], "content": _WORDS[0]}}]}
        ),
        json.dumps({"choices": [{"delta": {"content": _WORDS[1]}}]}),
        json.dumps({"choices": [{"delta": {"content": _WORDS[2]}}]}),
        json.dumps(
            {
                "choices": [{"finish_reason": "stop", "index": 0, "delta": {}}],
                "timings": {"predicted_per_second": _TPS, "predicted_n": _TOKENS},
            }
        ),
        "[DONE]",
    )


def _calling_body() -> bytes:
    return _sse(
        json.dumps({"choices": [{"delta": {"content": CONTRACT_ASIDE}}]}),
        json.dumps(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": CONTRACT_CALL.id,
                                    "function": {
                                        "name": CONTRACT_CALL.name,
                                        "arguments": _ARGUMENT_FRAGMENTS[0],
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ),
        json.dumps(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {"index": 0, "function": {"arguments": _ARGUMENT_FRAGMENTS[1]}}
                            ]
                        }
                    }
                ]
            }
        ),
        json.dumps({"choices": [{"finish_reason": "tool_calls", "index": 0, "delta": {}}]}),
        "[DONE]",
    )


@pytest.fixture
def scripted() -> BackendUnderTest:
    """Build the core twin, scripted with each world rather than asked to derive it."""

    def build(events: list[InferenceEvent]) -> ScriptedInferenceBackend:
        return ScriptedInferenceBackend([events], serves=[CONTRACT_MODEL])

    def deliberating() -> ScriptedInferenceBackend:
        return build(
            [
                *(ReasoningChunk(thought) for thought in _THOUGHTS),
                *(TextChunk(word) for word in _WORDS),
                DecodeStop(StopReason.FINISHED),
                DecodeCadence(tokens_per_second=_TPS, tokens=_TOKENS),
            ]
        )

    def calling() -> ScriptedInferenceBackend:
        return build([TextChunk(CONTRACT_ASIDE), DecodeStop(StopReason.CALLED), CONTRACT_CALL])

    def unreachable() -> ScriptedInferenceBackend:
        backend = build([TextChunk(CONTRACT_REPLY)])
        backend.fail_with(InferenceError("llama-server is not answering"))
        return backend

    async def aclose() -> None:
        return None

    return BackendUnderTest(
        deliberating=deliberating,
        calling=calling,
        wordless=partial(build, []),
        unreachable=unreachable,
        one_system_template=deliberating,
        aclose=aclose,
    )


@pytest.fixture
def adapter() -> BackendUnderTest:
    """Build the real adapter over a MockTransport serving the real llama-server bodies."""
    clients: list[httpx.AsyncClient] = []

    def over(handler: Callable[[httpx.Request], httpx.Response]) -> LlamaCppBackend:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        clients.append(client)
        manager = SingleResidentModelManager(resident_model=CONTRACT_MODEL, endpoint=_ENDPOINT)
        return LlamaCppBackend(manager, client)

    def build(body: bytes) -> LlamaCppBackend:
        return over(lambda _request: httpx.Response(200, content=body))

    def unreachable() -> LlamaCppBackend:
        def refuse(_request: httpx.Request) -> httpx.Response:
            msg = "no route to host"
            raise httpx.ConnectError(msg)

        return over(refuse)

    async def aclose() -> None:
        for client in clients:
            await client.aclose()

    return BackendUnderTest(
        deliberating=partial(build, _deliberating_body()),
        calling=partial(build, _calling_body()),
        wordless=partial(build, _sse("[DONE]")),
        unreachable=unreachable,
        one_system_template=lambda: over(
            TemplateServer(takes_several=False, reply=_deliberating_body())
        ),
        aclose=aclose,
    )


@pytest.mark.parametrize("check", STREAM_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.asyncio
async def test_scripted_backend_meets_the_stream_contract(
    scripted: BackendUnderTest, check: StreamCheck
) -> None:
    await check(scripted)
    await scripted.aclose()


@pytest.mark.parametrize("check", STREAM_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.asyncio
async def test_llamacpp_backend_meets_the_stream_contract(
    adapter: BackendUnderTest, check: StreamCheck
) -> None:
    await check(adapter)
    await adapter.aclose()


@pytest.mark.asyncio
async def test_the_adapter_leg_really_assembles_what_the_wire_split(
    adapter: BackendUnderTest,
) -> None:
    body = _calling_body().decode()
    assert json.dumps(CONTRACT_CALL.arguments) not in body
    assert CONTRACT_REPLY not in _deliberating_body().decode()
    assert CONTRACT_THINKING not in _deliberating_body().decode()
    events = await events_of(adapter.calling())
    await adapter.aclose()
    assert [event for event in events if isinstance(event, ToolCall)] == [CONTRACT_CALL]
