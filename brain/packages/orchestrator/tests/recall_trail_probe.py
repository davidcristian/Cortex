"""Measure how wide the recall trail's `dropped` field renders on a line a real stack wrote.

`VALUE_CHARS` is justified by clearing the widest value the tree attaches, and that value is this
field. The number behind that justification was drawn in process, from `uuid4` ids and cosine
scores synthesised by a script, with no store anywhere near it. A real `dropped` list carries the
ids the shipped record path minted and the cosines pgvector really returned, and the rendered width
is a function of both, so nothing had ever read the width off a line a live stack produced.

**This runs INSIDE the brain container**, which is the whole point: the lines it measures are
written by the shipped image, through the composition root's own wiring, the shipped
`LoggingRecallSink` and the shipped formatter. It is copied in and run rather than imported,
because the image carries no test tree. `docker compose ... cp` puts this file in as `/tmp/probe.py`
and `recall_corpus.py` beside it as `/tmp/recall_corpus.py`, and then:

    docker compose ... exec -T -e PYTHONPATH=/tmp brain python /tmp/probe.py

`just recall-width` is what does all of that, and `scripts/trailwidth.py` reads the width off the
captured output afterwards. Nothing here computes a statistic, for the reason the turn-cost block
driver computes none: the arithmetic behind a published number belongs in a gated tool.

**Two phases, because a trail line has two ways out of this container.**

* `direct` runs recalls through `build_memory`, the composition root's own memory wiring, read from
  this container's own environment. Every line lands on this process's stderr. It costs one rank
  each rather than a whole reply, which is what makes a sample of a few hundred affordable.
* `turns` opens `Converse` against the brain's own loopback seam, so the recall happens on the
  serving path and its line goes out on the container's own stream and through the log driver,
  where `docker compose logs brain` reads it. It costs a whole model reply per turn, so it is
  small, and its job is to say whether the cheap phase's lines are the lines a turn produces.

Every pass and every turn seeds a session scope of its own with all 41 notes of `recall_corpus`,
through `MemoryRecaller.record`, so the ids are minted by the shipped factory and the embeddings by
the real CPU embedder. Forty one notes against a pool of twenty is what makes the pool a real pool
rather than the whole store. Every scope is deleted on the way out through the same cascade the
session-delete path uses.
"""

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

# What gets asked, in three populations, and the breadth is the point rather than the count. The
# rendered width is the ids plus the cosines, and the id half varies by nothing at all, the shipped
# factory minting thirty six characters every time; so every bit of variance a run can show comes
# from the scores, and one query is one draw of twenty of them however many times it is repeated.
#
# The corpus's own questions come first. The population no note answers is deliberately included:
# a rank that keeps nothing drops the WHOLE pool, which is the widest this field ever gets, and an
# unanswerable question is how that case arises in life. The notes' own texts are asked as well,
# which is a real thing to ask (a question in the words the note was written in) and cheap breadth:
# it takes the distinct draws from thirty four to seventy five without touching what is stored.
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
    """Print progress on stdout, where no trail line ever lands."""
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
    """Return why this container can write no recall trail, or ``None`` when it can.

    The scope check earns its place: under global scoping every note this probe writes lands in
    the one space every conversation shares, and the cascade below refuses to sweep that space, so
    the corpus would stay in the brain's own memory indefinitely.
    """
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
    """Run the cheap phase: recalls through the composition root's wiring, one rank each."""
    for index in range(_DIRECT_PASSES):
        scope = f"trail-width-direct-{stamp}-{index}"
        scopes.append(scope)
        await _seed(recaller, scope)
        for question in _ASKED:
            await recaller.recall(question, k=DEFAULT_RECALL_K, session_id=scope)
        _say(f"probe: direct pass {index + 1}/{_DIRECT_PASSES} asked {len(_ASKED)} questions")


async def _served(recaller: MemoryRecaller, scopes: list[str], stamp: int) -> None:
    """Run real turns, whose trail lines go out through the container's log driver."""
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
    backend, close_backend = await build_inference_backend(InferenceConfig(), runtime.cortex_model)
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
