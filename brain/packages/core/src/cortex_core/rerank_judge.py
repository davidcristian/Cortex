"""The model-based recall rank: ask the resident model which candidates fit the query."""

import json
import logging
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
from cortex_core.stops import StopLedger

_logger = logging.getLogger(__name__)

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

CANDIDATE_CHARS = 400

_RANK_TURN_ID = "recall-rank"

# Sized from measurement rather than fixed: the JSON reply alone decoded 14 to 16 tokens for
# a single pick, and each further candidate adds a comma, a space and its digits. A fixed
# constant would start truncating the day a deployment recalls more, with nothing saying so.
RANK_ENVELOPE_TOKENS = 24
RANK_TOKENS_PER_CANDIDATE = 8


def rank_bounds(k: int) -> GenerationBounds:
    """The bounds for one rank request: no thinking, no trace, and room for ``k`` picks."""
    return GenerationBounds(
        max_tokens=RANK_ENVELOPE_TOKENS + RANK_TOKENS_PER_CANDIDATE * k,
        thinking=False,
        trace_tokens=0,
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


def parse_order(raw: str, *, pool_size: int, k: int) -> tuple[int, ...] | None:
    """The candidate numbers the model returned: in range, de-duplicated, truncated to ``k``."""
    try:
        order: object = json.loads(raw)["order"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    if not isinstance(order, list):
        return None
    listed = cast("list[object]", order)
    kept: list[int] = []
    for element in listed:
        if type(element) is int and 0 <= element < pool_size and element not in kept:
            kept.append(element)
    if listed and not kept:
        return None
    return tuple(kept[:k])


class JudgeRecallPolicy:
    """Rank the candidate pool by asking the model, falling back to another policy on failure."""

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
        self,
        hits: Sequence[ScoredMemory],
        *,
        query: str,
        now: datetime,
        k: int,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> Ranking:
        """Ask the model to order the pool: fall back on a failure, keep nothing on a refusal."""
        if not hits:
            # No candidates, so no ranking was possible and none was attempted: this path
            # writes no log line, unlike the two failures below.
            return await self._fallback.select(
                hits, query=query, now=now, k=k, session_id=session_id, turn_id=turn_id
            )
        stops = StopLedger()
        try:
            raw = await drain_text(
                self._backend,
                self._model,
                build_rank_messages(query, hits, k=k, at=now),
                schema=ORDER_ENVELOPE,
                bounds=rank_bounds(k),
                stops=stops,
            )
        except InferenceError:
            _logger.warning(
                "the model could not be asked to rank recall; falling back to the unjudged ranking",
                extra={"session_id": session_id, "turn_id": turn_id, "pool": len(hits), "k": k},
                exc_info=True,
            )
            return await self._fallback.select(
                hits, query=query, now=now, k=k, session_id=session_id, turn_id=turn_id
            )
        order = parse_order(raw, pool_size=len(hits), k=k)
        if order is None:
            _logger.warning(
                "the model returned no usable recall order; falling back to the unjudged ranking",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "pool": len(hits),
                    "k": k,
                    "capped": stops.capped,
                    "chars": len(raw),
                },
            )
            return await self._fallback.select(
                hits, query=query, now=now, k=k, session_id=session_id, turn_id=turn_id
            )
        if not order:
            return Ranking(hits=(), basis=RankBasis.DEMUR)
        return Ranking(hits=_keyed(hits, order), basis=RankBasis.VERDICT)


def _keyed(hits: Sequence[ScoredMemory], order: Sequence[int]) -> tuple[RankedMemory, ...]:
    """Pair each chosen candidate with its normalized placing: 1.0 for the best, down to 1/n."""
    count = len(order)
    return tuple(
        RankedMemory(hit=hits[candidate], key=(count - position) / count)
        for position, candidate in enumerate(order)
    )
