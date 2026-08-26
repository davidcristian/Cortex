"""How wide is the recall trail's `dropped` field on a line a real stack wrote?"""

import asyncio
import os
import sys
import time
from typing import cast

from grpc import aio
from recall_corpus import MEMORIES, QUESTIONS, UNRELATED

from cortex_core import MemoryRecaller, SystemClock
from cortex_core.turn_context import DEFAULT_RECALL_K
from cortex_orchestrator.builders import build_inference_backend
from cortex_orchestrator.config import BrainRuntimeConfig, InferenceConfig, MemoryConfig
from cortex_orchestrator.config_logging import configure_from_env
from cortex_orchestrator.memory_builders import build_memory
from cortex_seam import SEAM_TOKEN_HEADER, BrainServiceStub, ClientEvent, ServerEvent, UserTurn

_ASKED: tuple[str, ...] = (*QUESTIONS, *UNRELATED, *MEMORIES.values())

# How many passes over `_ASKED` each phase makes. The direct phase pays one rank per recall; the
# turns phase pays a whole reply, so it asks a slice rather than the whole list.
_DIRECT_PASSES = int(os.environ.get("CORTEX_TRAIL_DIRECT_PASSES", "3"))
_TURNS = int(os.environ.get("CORTEX_TRAIL_TURNS", "8"))
_SEAM = os.environ.get("CORTEX_TRAIL_SEAM", "127.0.0.1:50051")


def _metadata() -> tuple[tuple[str, str], ...] | None:
    token = os.environ.get("CORTEX_SEAM_TOKEN", "")
    return ((SEAM_TOKEN_HEADER, token),) if token else None


def _say(message: str) -> None:
    """Progress, on stdout, where no trail line ever lands."""
    print(message, flush=True)  # noqa: T201 -- a probe's only output channel


async def _turn(stub: BrainServiceStub, session_id: str, question: str) -> None:
    """Ask one question over the seam and drain the stream, so the turn really completes."""
    converse = stub.Converse  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    call = cast("aio.StreamStreamCall[ClientEvent, ServerEvent]", converse(metadata=_metadata()))
    await call.write(ClientEvent(session_id=session_id, user_turn=UserTurn(text=question)))
    await call.done_writing()
    async for event in call:
        if event.WhichOneof("event") == "error":
            msg = f"turn {session_id} failed: {event.error.code} {event.error.message}"
            raise AssertionError(msg)


def _unfit(config: MemoryConfig) -> str | None:
    """Why this container can write no recall trail, or ``None`` when it can."""
    if config.backend != "pgvector":
        return f"memory backend is {config.backend!r}, so no recall trail exists"
    if not config.recall_audit:
        return "CORTEX_MEMORY_RECALL_AUDIT is off, so no recall trail is written"
    if config.scope != "session":
        return f"CORTEX_MEMORY_SCOPE is {config.scope!r}; run this probe under 'session'"
    return None


async def _seed(recaller: MemoryRecaller, scope: str) -> None:
    """Write the whole corpus into ``scope`` through the shipped record path."""
    for text in MEMORIES.values():
        await recaller.record(text, session_id=scope)


async def _direct(recaller: MemoryRecaller, scopes: list[str], stamp: int) -> None:
    """The cheap phase: recalls through the composition root's own wiring, one rank each."""
    for index in range(_DIRECT_PASSES):
        scope = f"trail-width-direct-{stamp}-{index}"
        scopes.append(scope)
        await _seed(recaller, scope)
        for question in _ASKED:
            await recaller.recall(question, k=DEFAULT_RECALL_K, session_id=scope)
        _say(f"probe: direct pass {index + 1}/{_DIRECT_PASSES} asked {len(_ASKED)} questions")


async def _served(recaller: MemoryRecaller, scopes: list[str], stamp: int) -> None:
    """The answerable phase: real turns, whose trail lines go out through the log driver."""
    async with aio.insecure_channel(_SEAM) as channel:
        stub = BrainServiceStub(channel)
        for index in range(_TURNS):
            scope = f"trail-width-turn-{stamp}-{index}"
            scopes.append(scope)
            await _seed(recaller, scope)
            await _turn(stub, scope, _ASKED[index % len(_ASKED)])
            _say(f"probe: turn {index + 1}/{_TURNS} completed in scope {scope}")


async def _main() -> int:
    configure_from_env()
    runtime = BrainRuntimeConfig()
    memory_config = MemoryConfig()
    unfit = _unfit(memory_config)
    if unfit is not None:
        _say(f"probe: {unfit}")
        return 2
    backend, close_backend = build_inference_backend(InferenceConfig(), runtime.cortex_model)
    recaller, cascade, close_memory = await build_memory(
        memory_config, SystemClock(), backend, runtime.cortex_model
    )
    if recaller is None or cascade is None:
        _say("probe: the composition root built no recaller")
        return 2
    stamp = int(time.time())
    scopes: list[str] = []
    try:
        await _direct(recaller, scopes, stamp)
        await _served(recaller, scopes, stamp)
    finally:
        for scope in scopes:
            await cascade.delete_session_memories(scope)
        await close_memory()
        await close_backend()
    _say(f"probe: {_DIRECT_PASSES * len(_ASKED)} direct recalls and {_TURNS} turns, scopes cleared")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
