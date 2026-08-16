"""Drive the shared stop-reason contract over both implementations of the port.

The scripted twin and the real ``LlamaCppBackend`` pass the identical checks, which is the
ports-before-adapters gate for the finish-reason arm (AGENTS.md). The adapter's leg reads a
**real** llama-server body: the two final chunks below were copied from live runs of the shipped
CPU subagent tier on this repo's own machine (llama.cpp build ``b9879-72874f559``, gemma-4-E4B QAT
q4_0), one from a request capped at ``max_tokens: 8`` and one from an uncapped reply, so what the
parser is held to is bytes the server actually emits.

Mutations run against production code, each reverted and each with the whole ``packages`` suite
re-run, proving these checks can fail rather than trusting that they pass:

- dropping the ``finish_reason`` read from ``decode._stop`` reddens 14, which on this file is
  ``check_a_cut_completion_says_it_was_cut``, ``check_a_finished_completion_is_not_a_cut_one`` and
  ``check_the_stop_follows_the_text_it_explains`` on the adapter leg and **no scripted case**, which
  is the derived half doing its work;
- mapping ``"length"`` to ``StopReason.FINISHED`` reddens 4, the cap check on the adapter leg and
  the three cases in ``test_backend.py`` that read that word;
- reporting ``DecodeStop(StopReason.FINISHED)`` when no reason was read reddens 29, of which
  ``check_silence_is_a_legal_answer`` on the adapter leg is one. The other 28 are the point: every
  chunk before a stream's last carries no reason, so the mutation puts a stop after every delta in
  the suite. Silence is most of what a stream is, not a corner of it.

**Yielding the stop before the text in ``_chunk_events`` reddens 3, and none of them is
``check_the_stop_follows_the_text_it_explains``.** The cadence contract beside this one records the
identical finding about itself, and the cause is the same: a real final chunk carries its
``finish_reason`` on a content-less delta, so text and stop stay in order across chunks whatever
order the adapter yields them within one. What catches a reorder is
``test_a_stop_and_a_cadence_on_one_chunk_arrive_stop_first`` in ``test_backend.py``, where a chunk
carries both, which is why that case lives beside the adapter rather than here.
"""

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
    """The contract's derived half, stated once outside the shared checks.

    The scripted twin cannot fail this: it is handed a ``DecodeStop``. The adapter is handed bytes,
    so this pins that ``length`` was read out of a real llama.cpp final chunk and not out of
    anything the test built for it, and that the core's own word for it is nowhere on the wire,
    which is the whole reason the reason is a closed set rather than the string the server sent.
    """
    body = _body(_CAPPED_TAIL).decode()
    assert '"finish_reason":"length"' in body
    assert "capped" not in body
    events = await events_of(adapter.capped())
    await adapter.aclose()
    assert [event for event in events if isinstance(event, DecodeStop)] == [
        DecodeStop(StopReason.CAPPED)
    ]
