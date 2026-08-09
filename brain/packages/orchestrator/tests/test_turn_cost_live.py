"""What does a whole recalling turn cost, end to end over the seam, in ONE recall arm?

This is the committed form of the harness that moved `CORTEX_MEMORY_RECALL` to `judge`
(ADR-0038 turn-cost addendum), whose driver lived in a scratchpad and left the one measurement
in that ADR that names no reproducing test. The shape it settles is argued in that ADR's harness
addendum; what matters when reading this file is the division of labour it rests on, because that
explains every choice below:

* **This test measures exactly one block, and never restarts anything.** An arm here is a brain
  container configured one way, and changing it means recreating that container, which is a
  deployment step rather than an assertion. A pytest process that recreated its own subject would
  be instrument and operator at once, would need the whole compose file set spelled a second time
  inside a test, and would own a stack it did not bring up and could not restore. So the restart
  belongs to `just turn-cost`, which is committed and versioned like anything else, and this file
  is what that recipe runs once per block.
* **Because the arms live in separate processes, the sample has to outlive this one.** Each block
  writes its turns to a JSON file, and `scripts/contrast.py` reads the blocks afterwards and
  reports the paired bootstrap interval. That is why nothing here computes a statistic: the
  arithmetic behind the published number is the part that was unreproducible, so it lives in a
  gated tool with unit tests rather than inside an integration-marked print.
* **So this file asserts invariants only**, in the discipline of `test_fold_under_load_live.py`:
  every turn spoke and completed, every turn's scope is one the brain really recalled from and
  recorded into, and the corpus leaves nothing behind. No assertion depends on what the model says
  or on how long it took, because the timing IS the output and a harness that asserted a bound on
  it would be deciding the result in advance.

**The protocol.** Each turn runs in its own fresh session under `CORTEX_MEMORY_SCOPE=session`,
whose scope is pre-seeded with all 41 notes of `recall_corpus.py`, so every turn ranks an identical
corpus, no turn's recorded exchange reaches the next turn's pool, and the global memory space is
neither read nor written. Six questions, one per corpus category (the first of each in `QUESTIONS`
order, a stated rule rather than a hand pick, since the original run recorded which categories it
drew from but not which questions), repeated `CORTEX_TURN_COST_REPS` times. Repetitions are
**rep-major**: every question is asked once before any is asked twice, so drift over a block
spreads evenly across the questions instead of pooling inside one of them, which is what makes
blocking by question honest. One warmup turn runs first and is discarded, because the turn
immediately after a container recreate pays a cold gRPC channel, a cold asyncpg pool and the
model's first prompt eval, and letting that land inside a measured cell would bias one question's
mean in one arm only.

The 41 note embeddings are computed once per block and reused for every turn's scope. A vector is
a pure function of the note text and the embedding model, both fixed for a run, so caching changes
nothing about what is stored; it only keeps the seeding off the clock.

Integration-marked, so CI and the coverage gate never see it. Run it through the recipe, which
owns the restarts and the arms:

    just turn-cost

or, for a single block against an already-configured brain:

    cd brain && CORTEX_TURN_COST_ARM=judge CORTEX_TURN_COST_OUT=../measurements/probe.json \\
      uv run pytest -m integration --no-cov -s \\
      packages/orchestrator/tests/test_turn_cost_live.py
"""

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
from cortex_seam import SEAM_TOKEN_HEADER, BrainServiceStub, ClientEvent, ServerEvent, UserTurn

_SEAM_ENDPOINT = os.environ.get("CORTEX_SEAM_ENDPOINT", "127.0.0.1:50051")
# The loopback publishes of the memory override (docs/runbooks/memory-pgvector.md). The DSN
# default is that runbook's own, the one the live MemoryStore contract run also starts from.
_DSN = os.environ.get("CORTEX_MEMORY_DSN", "postgresql://cortex:cortex@127.0.0.1:5432/cortex")
_EMBEDDER = os.environ.get("CORTEX_MEMORY_EMBEDDER_ENDPOINT", "http://127.0.0.1:8081")

# Which arm this block measures. It is a LABEL on the sample file and not a control: the brain
# container is already running in some arm and this process cannot change that. Setting it wrong
# mislabels a block, which is why the recipe sets it in the same command that sets the container's.
_ARM = os.environ.get("CORTEX_TURN_COST_ARM", "unnamed")
_REPS = int(os.environ.get("CORTEX_TURN_COST_REPS", "8"))
_OUT = os.environ.get("CORTEX_TURN_COST_OUT", "")

# One question per category, the first of each in corpus order.
_QUESTIONS: tuple[tuple[str, Category], ...] = tuple(
    (next(q for q, (_, probed) in QUESTIONS.items() if probed is category), category)
    for category in Category
)
_CORPUS_SIZE = len(MEMORIES)


def _metadata() -> tuple[tuple[str, str], ...] | None:
    token = os.environ.get("CORTEX_SEAM_TOKEN", "")
    return ((SEAM_TOKEN_HEADER, token),) if token else None


@dataclass(frozen=True, slots=True)
class _Turn:
    """One measured turn: what was asked, and the two latencies the addendum reports."""

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
    """The block's sample as JSON text: the only thing this process produces for the report."""
    return (
        json.dumps(
            {
                "arm": _ARM,
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
async def test_one_turn_cost_block_over_the_live_seam() -> None:
    out = Path(_OUT or f"measurements/turn-cost-{_ARM}-{int(time.time())}.json")
    stamp = int(time.time())
    schedule = _schedule()
    scopes = [f"turn-cost-{_ARM}-{stamp}-{index}" for index in range(len(schedule))]
    turns: list[_Turn] = []
    store = await PgVectorMemoryStore.connect(_DSN)
    try:
        async with httpx.AsyncClient(timeout=60.0) as http:
            embedder = LlamaCppEmbedder(http, _EMBEDDER)
            vectors = {name: tuple(await embedder.embed(text)) for name, text in MEMORIES.items()}
        async with aio.insecure_channel(_SEAM_ENDPOINT) as channel:
            stub = BrainServiceStub(channel)
            for scope, (rep, question, category) in zip(scopes, schedule, strict=True):
                await _seed(store, scope, vectors)
                ttft, wall, answer = await _run_turn(stub, scope, question)
                # The scope a turn recalls from is the scope it records into, so a turn that
                # really had memory on leaves MORE rows than it was handed. Equality here means
                # the container ran with memory off and the block measured a plain turn while
                # calling itself a recalling one.
                left = await store.delete_scope(scope)
                assert left > _CORPUS_SIZE, (
                    f"scope {scope} held {left} rows against the {_CORPUS_SIZE} seeded: the brain"
                    " recorded nothing there, so memory was not on for this block"
                )
                assert answer.strip(), f"turn {scope} answered with nothing at all"
                if rep >= 0:
                    turns.append(_Turn(question, category.name, rep, ttft, wall, len(answer)))
    finally:
        for scope in scopes:  # idempotent: the loop above already emptied every scope it reached
            await store.delete_scope(scope)
        await store.aclose()
    assert len(turns) == _REPS * len(_QUESTIONS), "the block did not run the protocol it claims"
    out.parent.mkdir(parents=True, exist_ok=True)
    # ASYNC240: one small write on an idle loop, after the last timed turn is already over.
    out.write_text(_sample(turns), encoding="utf-8")  # noqa: ASYNC240
    print(f"\n{_ARM} block: {len(turns)} turns over {len(_QUESTIONS)} questions -> {out}")  # noqa: T201
