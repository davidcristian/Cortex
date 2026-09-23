import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
import pytest
from grpc import aio
from recall_corpus import MEMORIES, QUESTIONS, Category

from cortex_core import MemoryRecord
from cortex_embedding import LlamaCppEmbedder
from cortex_memory import PgVectorMemoryStore
from cortex_seam import RPC_TOKEN_HEADER, BrainServiceStub, ClientEvent, ServerEvent, UserTurn

_RPC_ENDPOINT = os.environ.get("CORTEX_SEAM_ENDPOINT", "127.0.0.1:50051")
_DSN = os.environ.get("CORTEX_MEMORY_DSN", "postgresql://cortex:cortex@127.0.0.1:5432/cortex")
_EMBEDDER = os.environ.get("CORTEX_MEMORY_EMBEDDER_ENDPOINT", "http://127.0.0.1:8081")

# A label on the sample file rather than a setting: the brain container is already running in
# one configuration and this process cannot change that, so a wrong value mislabels a block.
_VARIANT = os.environ.get("CORTEX_TURN_COST_ARM", "unnamed")
_REPS = int(os.environ.get("CORTEX_TURN_COST_REPS", "8"))
_OUT = os.environ.get("CORTEX_TURN_COST_OUT", "")

_QUESTIONS: tuple[tuple[str, Category], ...] = tuple(
    (next(q for q, (_, probed) in QUESTIONS.items() if probed is category), category)
    for category in Category
)
_CORPUS_SIZE = len(MEMORIES)


def _metadata() -> tuple[tuple[str, str], ...] | None:
    token = os.environ.get("CORTEX_SEAM_TOKEN", "")
    return ((RPC_TOKEN_HEADER, token),) if token else None


@dataclass(frozen=True, slots=True)
class _Turn:
    """One measured turn: what was asked, and the two latencies the measurement reports."""

    question: str
    category: str
    rep: int
    ttft: float
    wall: float
    chars: int


def _schedule() -> list[tuple[int, str, Category]]:
    """The block's turns in order: one discarded warmup (rep -1), then rep-major repetitions."""
    warmup = [(-1, *_QUESTIONS[0])]
    return warmup + [
        (rep, question, category) for rep in range(_REPS) for question, category in _QUESTIONS
    ]


async def _run_turn(
    stub: BrainServiceStub, session_id: str, question: str
) -> tuple[float, float, str]:
    """Open one Converse stream, ask ``question``, and time the first token and the completion."""
    converse = stub.Converse  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    call = cast("aio.StreamStreamCall[ClientEvent, ServerEvent]", converse(metadata=_metadata()))
    started = time.monotonic()
    await call.write(ClientEvent(session_id=session_id, user_turn=UserTurn(text=question)))
    await call.done_writing()
    first: float | None = None
    completed: float | None = None
    answer = ""
    async for event in call:
        kind = event.WhichOneof("event")
        if kind == "text_delta":
            first = first if first is not None else time.monotonic()
            answer += event.text_delta.text
        elif kind == "turn_complete":
            completed = time.monotonic()
        elif kind == "error":
            msg = f"turn {session_id} failed on the wire: {event.error.code} {event.error.message}"
            raise AssertionError(msg)
    assert first is not None, f"turn {session_id} never produced a token"
    assert completed is not None, f"turn {session_id} never completed"
    return first - started, completed - started, answer


async def _seed(
    store: PgVectorMemoryStore, scope: str, vectors: dict[str, tuple[float, ...]]
) -> None:
    """Write the whole corpus into ``scope``, which under session scoping IS the session id."""
    at = datetime.now(UTC)
    for note_id, text in MEMORIES.items():
        record = MemoryRecord(
            id=f"{scope}-{note_id}", text=text, embedding=vectors[note_id], at=at, scope=scope
        )
        await store.add(record)


def _sample(turns: list[_Turn]) -> str:
    """Return the block's sample as JSON text, the only output this process leaves behind."""
    return (
        json.dumps(
            {
                "arm": _VARIANT,
                "recorded_at": datetime.now(UTC).isoformat(),
                "reps": _REPS,
                "corpus_size": _CORPUS_SIZE,
                "turns": [
                    {
                        "question": turn.question,
                        "category": turn.category,
                        "rep": turn.rep,
                        "ttft": turn.ttft,
                        "wall": turn.wall,
                        "chars": turn.chars,
                    }
                    for turn in turns
                ],
            },
            indent=2,
        )
        + "\n"
    )


@pytest.mark.integration
async def test_one_turn_cost_block_over_the_live_rpc() -> None:
    out = Path(_OUT or f"measurements/turn-cost-{_VARIANT}-{int(time.time())}.json")
    stamp = int(time.time())
    schedule = _schedule()
    scopes = [f"turn-cost-{_VARIANT}-{stamp}-{index}" for index in range(len(schedule))]
    turns: list[_Turn] = []
    store = await PgVectorMemoryStore.connect(_DSN)
    try:
        async with httpx.AsyncClient(timeout=60.0) as http:
            embedder = LlamaCppEmbedder(http, _EMBEDDER)
            vectors = {name: tuple(await embedder.embed(text)) for name, text in MEMORIES.items()}
        async with aio.insecure_channel(_RPC_ENDPOINT) as channel:
            stub = BrainServiceStub(channel)
            for scope, (rep, question, category) in zip(scopes, schedule, strict=True):
                await _seed(store, scope, vectors)
                ttft, wall, answer = await _run_turn(stub, scope, question)
                left = await store.delete_scope(scope)
                assert left > _CORPUS_SIZE, (
                    f"scope {scope} held {left} rows against the {_CORPUS_SIZE} seeded: the brain"
                    " recorded nothing there, so memory was not on for this block"
                )
                assert answer.strip(), f"turn {scope} answered with nothing at all"
                if rep >= 0:
                    turns.append(_Turn(question, category.name, rep, ttft, wall, len(answer)))
    finally:
        for scope in scopes:
            await store.delete_scope(scope)
        await store.aclose()
    assert len(turns) == _REPS * len(_QUESTIONS), "the block did not run the protocol it claims"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_sample(turns), encoding="utf-8")  # noqa: ASYNC240
    print(f"\n{_VARIANT} block: {len(turns)} turns over {len(_QUESTIONS)} questions -> {out}")  # noqa: T201
