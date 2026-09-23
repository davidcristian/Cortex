import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest
from progress_contract import ALL_CHECKS, Check, SinkUnderTest

from cortex_core import RecordingProgressSink, StatusUpdate
from cortex_orchestrator import RpcProgressSink
from cortex_orchestrator.converse_stream import to_server_event

if TYPE_CHECKING:
    from cortex_seam import ServerEvent

type Build = Callable[[], SinkUnderTest]


def _recording() -> SinkUnderTest:
    sink = RecordingProgressSink()
    return SinkUnderTest(
        sink=sink,
        sent=lambda: [
            (event.state, event.detail) for event in sink.events if isinstance(event, StatusUpdate)
        ],
        current=sink.waits.current,
    )


def _rpc() -> SinkUnderTest:
    emitted: list[ServerEvent] = []
    sink = RpcProgressSink(emitted.append, asyncio.Semaphore(16), to_wire=to_server_event)
    return SinkUnderTest(
        sink=sink,
        sent=lambda: [
            (event.status.state, event.status.detail)
            for event in emitted
            if event.WhichOneof("event") == "status"
        ],
        current=sink.current,
    )


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.parametrize("build", [_recording, _rpc], ids=["recording", "rpc"])
async def test_the_contract_holds(check: Check, build: Build) -> None:
    await check(build())
