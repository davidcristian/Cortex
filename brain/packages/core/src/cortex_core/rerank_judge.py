"""The model-based recall rank: ask the resident model which candidates answer the query (ADR-0038).
"""

import json
from collections.abc import Sequence
from datetime import datetime
from typing import cast

from cortex_core.conversation import Message, Role
from cortex_core.drain import drain_text
from cortex_core.errors import InferenceError
from cortex_core.inference import GenerationBounds, JsonSchema
from cortex_core.memory import ScoredMemory
from cortex_core.ports import InferenceBackend
from cortex_core.ranking import RankBasis, RankedMemory, Ranking
from cortex_core.rerank import RAW_RECALL_POLICY, RecallPolicy

# The reply shape. An array of candidate numbers, best first, and nothing else: there is no
# grammatical position for an explanation, so the parse is a list lookup rather than prose mining.
ORDER_ENVELOPE: JsonSchema = {
    "type": "object",
    "properties": {"order": {"type": "array", "items": {"type": "integer"}}},
    "required": ["order"],
    "additionalProperties": False,
}

_INSTRUCTION = (
    "You are ranking remembered notes for how well each one helps answer a question. "
    "Reply with the numbers of the notes that help, best first, and leave out the ones "
    "that do not help at all."
)

# How much of a candidate to show the model. Recall candidates are single exchanges, so this holds
# whole ones in practice, and it bounds the prompt when a long one turns up.
CANDIDATE_CHARS = 400

# The prompt is not a conversation turn, so its ``turn_id`` is a constant rather than a real one:
# nothing persists these messages, and a borrowed turn id would read as this turn in a log.
_RANK_TURN_ID = "recall-rank"

RANK_ENVELOPE_TOKENS = 24
RANK_TOKENS_PER_CANDIDATE = 8


def rank_bounds(k: int) -> GenerationBounds:
    """The bounds one rank request carries: no thinking, and room for ``k`` numbered picks."""
    return GenerationBounds(
        max_tokens=RANK_ENVELOPE_TOKENS + RANK_TOKENS_PER_CANDIDATE * k, thinking=False
    )


def build_rank_messages(
    query: str, hits: Sequence[ScoredMemory], *, k: int, at: datetime
) -> list[Message]:
    """The one-message ranking prompt: the instruction, the question, then the numbered notes."""
    listed = "\n".join(
        f"{index}. {hit.record.text[:CANDIDATE_CHARS]}" for index, hit in enumerate(hits)
    )
    body = f"{_INSTRUCTION}\n\nQuestion: {query}\n\nNotes:\n{listed}\n\nReply with at most {k}."
    return [Message(role=Role.USER, text=body, at=at, turn_id=_RANK_TURN_ID)]


def parse_order(raw: str, *, pool_size: int, k: int) -> tuple[int, ...]:
    """The candidate numbers the model returned: in range, de-duplicated, truncated to ``k``."""
    try:
        order: object = json.loads(raw)["order"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return ()
    if not isinstance(order, list):
        return ()
    kept: list[int] = []
    for element in cast("list[object]", order):
        if type(element) is int and 0 <= element < pool_size and element not in kept:
            kept.append(element)
    return tuple(kept[:k])


class JudgeRecallPolicy:
    """Rank the candidate pool by asking the model, falling back to another policy when it cannot.
    """

    def __init__(
        self,
        backend: InferenceBackend,
        model: str,
        *,
        pool_factor: int,
        fallback: RecallPolicy = RAW_RECALL_POLICY,
    ) -> None:
        if pool_factor < 1:
            msg = "pool_factor must be at least 1"
            raise ValueError(msg)
        self._backend = backend
        self._model = model
        self._pool_factor = pool_factor
        self._fallback = fallback

    def candidate_k(self, k: int) -> int:
        """Over-fetch a pool ``pool_factor`` times wider than the returned ``k``."""
        return k * self._pool_factor

    async def select(
        self, hits: Sequence[ScoredMemory], *, query: str, now: datetime, k: int
    ) -> Ranking:
        """Ask the model to order the pool; fall back on any failure to reach or parse an answer."""
        if not hits:
            return await self._fallback.select(hits, query=query, now=now, k=k)
        try:
            raw = await drain_text(
                self._backend,
                self._model,
                build_rank_messages(query, hits, k=k, at=now),
                schema=ORDER_ENVELOPE,
                bounds=rank_bounds(k),
            )
        except InferenceError:
            return await self._fallback.select(hits, query=query, now=now, k=k)
        order = parse_order(raw, pool_size=len(hits), k=k)
        if not order:
            return await self._fallback.select(hits, query=query, now=now, k=k)
        return Ranking(hits=_keyed(hits, order), basis=RankBasis.VERDICT)


def _keyed(hits: Sequence[ScoredMemory], order: Sequence[int]) -> tuple[RankedMemory, ...]:
    """Pair each chosen candidate with its normalized placing: 1.0 for the best, down to 1/n."""
    count = len(order)
    return tuple(
        RankedMemory(hit=hits[candidate], key=(count - position) / count)
        for position, candidate in enumerate(order)
    )
