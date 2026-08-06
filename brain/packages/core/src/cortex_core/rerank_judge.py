"""The model-based recall rank: ask the resident model which candidates answer the query (ADR-0038).

The heuristic policies rank by geometry (cosine, a recency decay, a redundancy penalty). None of
them reads what a memory *says*, so a candidate worded unlike the query but answering it loses to
one that merely echoes its vocabulary. This policy hands the over-fetched pool to the model as a
numbered list and takes back an ordering, under a JSON-schema-constrained request so the reply
cannot arrive as prose (the ADR-0028 mechanism).

It lives in the core because it depends on nothing but ports, exactly like ``SubagentRunner``. It is
the reason ``RecallPolicy.select`` is ``async`` at all, and it obeys the selection-time lease
discipline: the model call goes through ``drain_text``, which closes its stream in a ``finally``, so
the turn's own reply acquires the GPU lease as the second acquire of a sequence and never nests.
The same call carries ``rank_bounds(k)``, so the request asks for the order alone rather than for
the deliberation ``drain_text`` drops before this module sees it.
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

# How far a rank's request may go (ADR-0038 bounded-side-calls addendum). **Thinking off** for the
# same reason as every other in-turn side call: ``drain_text`` drops the deliberation unread.
# Measured on the shipped cortex over six questions against ten notes, thinking on decoded 448 to
# 613 tokens for 18.4 s per recall; off, it decoded 12 to 22 tokens for 0.9 s, and returned the
# identical order for every question, so this bound costs the ranking nothing.
#
# **The cap is computed from ``k`` rather than fixed**, because unlike prose this reply's length
# is known in advance: ``ORDER_ENVELOPE`` admits ``{"order": [n, ...]}`` and nothing else, so the
# only thing that varies is how many numbers the caller allowed. The envelope's own punctuation
# measured 14 to 16 tokens for a single pick (JSON decodes at roughly a token per character), and
# each further candidate adds a comma, a space and its digits. A fixed constant sized for today's
# ``k`` of 5 would quietly start truncating the day a deployment recalls more, which is the failure
# a formula cannot have.
RANK_ENVELOPE_TOKENS = 24
RANK_TOKENS_PER_CANDIDATE = 8


def rank_bounds(k: int) -> GenerationBounds:
    """The bounds one rank request carries: no thinking, and room for ``k`` numbered picks.

    **Running into the cap degrades to the fallback policy, never to a mangled order.** A cut
    reply is not JSON (measured: a rank capped below its answer came back ``{"order":``), so
    ``parse_order`` returns empty and ``select`` falls back exactly as it does for an unreachable
    model, with the fallback's own basis on the ranking so the audit trail says the model did not
    rank this one. That is why the cap is generous rather than snug: a cap reached costs the whole
    judgement, not a candidate off the end.
    """
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
    """The candidate numbers the model returned: in range, de-duplicated, truncated to ``k``.

    Returns empty for anything unusable (not JSON, not the envelope, an ``order`` that is not a
    list), which is the one signal the caller needs, since every unusable reply takes the same
    fallback. Individual bad elements are dropped rather than voiding the answer: a model that
    hallucinates note 99 has still usefully ranked the rest, and refusing the whole reply over one
    element throws away a good rank. ``bool`` is an ``int`` in Python and a JSON ``true`` is not a
    note number, which is why the element check is on the exact type.
    """
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

    ``candidate_k`` over-fetches ``k * pool_factor``, like the heuristic policies, so the model gets
    a pool worth judging. ``select`` sends that pool and turns the returned order into keys spread
    evenly over ``(0, 1]``, best first, on the ``VERDICT`` basis: the model gives a placing rather
    than a score, and a normalized placing is the honest reading of one.

    ``fallback`` (default the raw top-k cosine) runs whenever the model cannot be used or believed:
    an empty pool, an ``InferenceError``, a reply outside the envelope, or an order that parses to
    nothing usable. The ranking then carries the fallback's own basis, so the audit
    trail says what actually ranked rather than what was configured, which is the difference
    between an observable rank and a hopeful one.
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
