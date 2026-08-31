"""Drive the shared decode-cadence contract over both implementations of the port.

The scripted twin and the real ``LlamaCppBackend`` pass the identical checks, which is the
ports-before-adapters gate for the cadence arm (AGENTS.md). The adapter's leg reads a **real**
llama-server body: the ``timings`` object below was copied from a live run of the shipped stack on
this repo's own card (llama.cpp build ``b10298-15586e2d7``), only its two watched numbers changed
to the contract's, so what the parser is held to is bytes the server actually emits.

Mutations run against this file, each reverted, proving the checks can fail rather than trusting
that they pass:

- dropping the ``timings`` object from the adapter's final chunk fails
  ``check_reports_the_servers_rate`` and ``check_cadence_closes_the_stream`` on the adapter leg
  and neither scripted case, which is the derived half doing its work;
- yielding the cadence before the text in ``LlamaCppBackend.stream`` fails
  ``check_cadence_closes_the_stream`` alone;
- making ``_non_negative`` accept a bool lets ``"predicted_per_second": true`` through as 1.0,
  which is what ``test_backend.py``'s own cadence cases pin.
"""

import json
from datetime import UTC, datetime
from functools import partial

import httpx
import pytest
from cadence_contract import (
    CADENCE_CHECKS,
    CONTRACT_MODEL,
    CONTRACT_TOKENS,
    CONTRACT_TPS,
    BackendUnderTest,
    CadenceCheck,
)

from cortex_core import (
    DecodeCadence,
    InferenceBackend,
    InferenceEvent,
    Message,
    Role,
    ScriptedInferenceBackend,
    SingleResidentModelManager,
    TextChunk,
)
from cortex_inference import LlamaCppBackend

_ENDPOINT = "http://model-host:8081"

# One llama-server streaming body, verbatim in shape from a live run: three content deltas and a
# final chunk whose `choices` are present but empty of delta, carrying the timings object.
_DELTAS = ("the ", "measured ", "answer")
_TIMINGS = json.dumps(
    {
        "cache_n": 0,
        "prompt_n": 25,
        "prompt_ms": 104.538,
        "prompt_per_token_ms": 4.18152,
        "prompt_per_second": 239.1474870382062,
        "predicted_n": CONTRACT_TOKENS,
        "predicted_ms": 1297.264,
        "predicted_per_token_ms": 16.215799999999998,
        "predicted_per_second": CONTRACT_TPS,
    }
)


def _body(*, cadence: bool) -> bytes:
    chunks = [f'{{"choices":[{{"delta":{{"content":"{delta}"}}}}]}}' for delta in _DELTAS]
    tail = f',"timings":{_TIMINGS}' if cadence else ""
    chunks.append(f'{{"choices":[{{"finish_reason":"stop","index":0,"delta":{{}}}}]{tail}}}')
    chunks.append("[DONE]")
    return "".join(f"data: {chunk}\n\n" for chunk in chunks).encode()


@pytest.fixture
def scripted() -> BackendUnderTest:
    """Build the core twin, scripted with the world-condition rather than asked to derive it."""

    def build(*, cadence: bool) -> InferenceBackend:
        events: list[InferenceEvent] = [TextChunk(delta) for delta in _DELTAS]
        if cadence:
            events.append(DecodeCadence(tokens_per_second=CONTRACT_TPS, tokens=CONTRACT_TOKENS))
        return ScriptedInferenceBackend([events])

    async def aclose() -> None:
        return None

    return BackendUnderTest(
        with_timings=partial(build, cadence=True),
        without_timings=partial(build, cadence=False),
        aclose=aclose,
    )


@pytest.fixture
def adapter() -> BackendUnderTest:
    """Build the real adapter over a MockTransport serving the real llama-server body."""
    clients: list[httpx.AsyncClient] = []

    def build(*, cadence: bool) -> InferenceBackend:
        def handle(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=_body(cadence=cadence))

        client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        clients.append(client)
        manager = SingleResidentModelManager(resident_model=CONTRACT_MODEL, endpoint=_ENDPOINT)
        return LlamaCppBackend(manager, client)

    async def aclose() -> None:
        for client in clients:
            await client.aclose()

    return BackendUnderTest(
        with_timings=partial(build, cadence=True),
        without_timings=partial(build, cadence=False),
        aclose=aclose,
    )


@pytest.mark.parametrize("check", CADENCE_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.asyncio
async def test_scripted_backend_meets_the_cadence_contract(
    scripted: BackendUnderTest, check: CadenceCheck
) -> None:
    await check(scripted)
    await scripted.aclose()


@pytest.mark.parametrize("check", CADENCE_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.asyncio
async def test_llamacpp_backend_meets_the_cadence_contract(
    adapter: BackendUnderTest, check: CadenceCheck
) -> None:
    await check(adapter)
    await adapter.aclose()


@pytest.mark.asyncio
async def test_the_adapter_leg_really_parses_the_servers_own_json(
    adapter: BackendUnderTest,
) -> None:
    """The adapter reads the rate and the token count out of the server's own JSON.

    This is the contract's derived half, stated once outside the shared checks. The scripted twin
    cannot fail it, because it is handed a ``DecodeCadence``. The adapter is handed bytes, so this
    pins that ``predicted_per_second`` and ``predicted_n`` were read out of a real llama.cpp
    ``timings`` object and not out of anything the test built for it.
    """
    body = _body(cadence=True).decode()
    assert '"predicted_per_second"' in body
    assert '"timings"' in body
    backend = adapter.with_timings()
    messages = [
        Message(role=Role.USER, text="how fast", at=datetime(2026, 8, 8, tzinfo=UTC), turn_id="t")
    ]
    cadences = [
        event
        async for event in backend.stream(CONTRACT_MODEL, messages)
        if isinstance(event, DecodeCadence)
    ]
    await adapter.aclose()
    assert cadences == [DecodeCadence(tokens_per_second=CONTRACT_TPS, tokens=CONTRACT_TOKENS)]
