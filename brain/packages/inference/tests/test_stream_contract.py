"""Drive the shared streaming contract over both implementations of the port.

The scripted twin and the real ``LlamaCppBackend`` pass the identical checks, which is the
ports-before-adapters gate for the stream itself (AGENTS.md). The adapter's leg reads llama-server
bodies in the shapes ``test_backend.py`` records beside it from live runs: a reasoning model's
stream, where one chunk carries the last thought and the first word together; a tool-calling one
whose arguments string is split across two chunks; a role-only opening chunk and a delta-less final
chunk, which are what the engine pads a stream with; and the two ``finish_reason`` words read off
the shipped CPU tier on build ``b9879-72874f559``.

``EchoInferenceBackend`` is deliberately not a third leg, though it is shipped wiring rather than a
test double. It cannot be put into three of the four worlds: it has no thinking, it calls no tool,
and it always answers, so the only builder it could satisfy is the failing one, and teaching it the
others would turn a backend a GPU-less deployment really runs into a test stub, which is the same
argument ``fakes_inference.py`` makes about the cadence it must never fabricate. What the echo owes
is held by ``core/tests/test_fakes.py``, beside the script it is.

Mutations run against production code, each reverted and each with the whole ``packages`` suite
re-run, proving these checks can fail rather than trusting that they pass. They are recorded in the
architecture ADR's addendum on the contract-test half of decision 2, port by port.
"""

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

# The completion's own decode rate, present so the pair of closing events can be observed together.
# The numbers say nothing here; what they mean is the cadence contract's subject.
_TPS = 24.61
_TOKENS = 12

# The deliberating world, as the wire carries it: a role-only opening chunk that says nothing, the
# thinking, one chunk carrying the last thought beside the first word, the rest of the reply, and a
# final chunk holding both closing facts.
_THOUGHTS = ("let me ", "check")
_WORDS = ("The ", "answer ", "is here")

# The calling world, as the wire carries it: the model says something, then streams one function
# call whose arguments arrive as two fragments, and the server closes on `tool_calls`.
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
    """The core twin, scripted with each world rather than asked to derive it.

    Every twin here is told it stands for a deployment serving ``CONTRACT_MODEL`` alone, which is
    the wiring the adapter leg gets from its ``SingleResidentModelManager``. Without it the two
    legs would disagree about an id no deployment serves, the fake answering where the adapter
    refuses.
    """

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
        aclose=aclose,
    )


@pytest.fixture
def adapter() -> BackendUnderTest:
    """The real adapter over a MockTransport serving the real llama-server bodies."""
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
    """The contract's derived half, stated once outside the shared checks.

    The scripted twin cannot fail this: it is handed a whole ``ToolCall`` and whole chunks. The
    adapter is handed bytes in which neither the arguments nor the reply exists as one value, so
    this pins that both were assembled here rather than written down for it.
    """
    body = _calling_body().decode()
    assert json.dumps(CONTRACT_CALL.arguments) not in body
    assert CONTRACT_REPLY not in _deliberating_body().decode()
    assert CONTRACT_THINKING not in _deliberating_body().decode()
    events = await events_of(adapter.calling())
    await adapter.aclose()
    assert [event for event in events if isinstance(event, ToolCall)] == [CONTRACT_CALL]
