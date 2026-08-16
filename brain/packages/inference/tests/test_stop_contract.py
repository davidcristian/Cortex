"""Drive the shared stop-reason contract over both implementations of the port."""

from functools import partial

import httpx
import pytest
from stop_contract import (
    STOP_CHECKS,
    BackendUnderTest,
    StopCheck,
    events_of,
)

from cortex_core import (
    DecodeStop,
    InferenceBackend,
    InferenceEvent,
    ScriptedInferenceBackend,
    SingleResidentModelManager,
    StopReason,
    TextChunk,
)
from cortex_inference import LlamaCppBackend

_ENDPOINT = "http://llama-subagent:8082"

# The reply text every arm streams, so a check comparing two arms compares only their endings.
_DELTAS = ("The ", "sea ", "is")

# The final chunk of a real capped run and of a real finished one, verbatim in shape from live
# requests to the shipped CPU tier; only the ``timings`` object is dropped, this contract being
# about the other closing event and the two being independent.
_CAPPED_TAIL = (
    '{"choices":[{"finish_reason":"length","index":0,"delta":{}}],"object":"chat.completion.chunk"}'
)
_FINISHED_TAIL = (
    '{"choices":[{"finish_reason":"stop","index":0,"delta":{}}],"object":"chat.completion.chunk"}'
)


def _body(tail: str | None) -> bytes:
    chunks = [
        f'{{"choices":[{{"finish_reason":null,"delta":{{"content":"{d}"}}}}]}}' for d in _DELTAS
    ]
    if tail is not None:
        chunks.append(tail)
    chunks.append("[DONE]")
    return "".join(f"data: {chunk}\n\n" for chunk in chunks).encode()


@pytest.fixture
def scripted() -> BackendUnderTest:
    """The core twin, scripted with the world-condition rather than asked to derive it."""

    def build(*, reason: StopReason | None) -> InferenceBackend:
        events: list[InferenceEvent] = [TextChunk(delta) for delta in _DELTAS]
        if reason is not None:
            events.append(DecodeStop(reason))
        return ScriptedInferenceBackend([events])

    async def aclose() -> None:
        return None

    return BackendUnderTest(
        finished=partial(build, reason=StopReason.FINISHED),
        capped=partial(build, reason=StopReason.CAPPED),
        silent=partial(build, reason=None),
        aclose=aclose,
    )


@pytest.fixture
def adapter() -> BackendUnderTest:
    """The real adapter over a MockTransport serving the real llama-server body."""
    clients: list[httpx.AsyncClient] = []

    def build(*, tail: str | None) -> InferenceBackend:
        def handle(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=_body(tail))

        client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        clients.append(client)
        manager = SingleResidentModelManager(resident_model="subagent", endpoint=_ENDPOINT)
        return LlamaCppBackend(manager, client)

    async def aclose() -> None:
        for client in clients:
            await client.aclose()

    return BackendUnderTest(
        finished=partial(build, tail=_FINISHED_TAIL),
        capped=partial(build, tail=_CAPPED_TAIL),
        silent=partial(build, tail=None),
        aclose=aclose,
    )


@pytest.mark.parametrize("check", STOP_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.asyncio
async def test_scripted_backend_meets_the_stop_contract(
    scripted: BackendUnderTest, check: StopCheck
) -> None:
    await check(scripted)
    await scripted.aclose()


@pytest.mark.parametrize("check", STOP_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.asyncio
async def test_llamacpp_backend_meets_the_stop_contract(
    adapter: BackendUnderTest, check: StopCheck
) -> None:
    await check(adapter)
    await adapter.aclose()


@pytest.mark.asyncio
async def test_the_adapter_leg_really_reads_the_servers_own_word(
    adapter: BackendUnderTest,
) -> None:
    """The contract's derived half, stated once outside the shared checks."""
    body = _body(_CAPPED_TAIL).decode()
    assert '"finish_reason":"length"' in body
    assert "capped" not in body
    events = await events_of(adapter.capped())
    await adapter.aclose()
    assert [event for event in events if isinstance(event, DecodeStop)] == [
        DecodeStop(StopReason.CAPPED)
    ]
