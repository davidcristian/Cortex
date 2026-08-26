"""The model-based recall rank: ask the resident model which candidates answer the query (ADR-0038).

The heuristic policies rank by geometry (cosine, a recency decay, a redundancy penalty). None of
them reads what a memory *says*, so a candidate worded unlike the query but answering it loses to
one that merely echoes its vocabulary. This policy hands the over-fetched pool to the model as a
numbered list and takes back an ordering, under a JSON-schema-constrained request so the reply
cannot arrive as prose (the ADR-0028 mechanism).

It is also the only policy that can answer that nothing in the pool helps, which it returns as an
empty ranking on the ``DEMUR`` basis rather than as a fallback (ADR-0038 abstention addendum): a
geometric policy always has a nearest neighbour to offer, so a question memory cannot answer is a
question only a reader can decline.

It lives in the core because it depends on nothing but ports, exactly like ``SubagentRunner``. It is
the reason ``RecallPolicy.select`` is ``async`` at all, and it obeys the selection-time lease
discipline: the model call goes through ``drain_text``, which closes its stream in a ``finally``, so
the turn's own reply acquires the GPU lease as the second acquire of a sequence and never nests.
The same call carries ``rank_bounds(k)``, so the request asks for the order alone rather than for
the deliberation ``drain_text`` drops before this module sees it.

**A rank that does not happen says so** (ADR-0038 unjudged-rank addendum). Four things end a
``select`` without a verdict, and two of them are faults that each log their own warning: a backend
that could not be asked, and a reply no order could be read out of. The other two are silent
because neither is a fault. An empty pool is a no-op with nothing to judge. An empty ``order`` is
the model judging and declining, which the recall trail reports as the ``DEMUR`` basis beside every
other per-recall fact. So a line from here always means the one thing, that the rank a deployment
configured did not run, and no line means the pool was judged or there was nothing to judge.

**Both warnings name the recall they happened to** (ADR-0038 named-recall addendum). ``session_id``
is the id the port now carries, spelled the way ``LoggingRecallSink`` spells it, because the trail
line for the very same recall is what an operator pairs a fallback with; without it a burst of
fallbacks on a brain serving several conversations could not be attributed to any of them. It is
the caller's opaque handle and nothing else: the pool and the ``query`` are conversation content,
and no line here has ever carried either. A caller that gave no id logs ``session_id=None``, which
says the recall arrived unnamed rather than leaving a reader to wonder whether the field exists.
Both this pair and the trail spelled it ``session`` until the brain settled on one name per work
identity, which is the stamp's (ADR-0009 one-vocabulary addendum); the pairing argument is
unchanged by the rename, the two surfaces having moved together.
"""

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
    ``parse_order`` returns ``None`` and ``select`` falls back exactly as it does for an unreachable
    model, with the fallback's own basis on the ranking so the audit trail says the model did not
    rank this one. That is why the cap is generous rather than snug: a cap reached costs the whole
    judgement, not a candidate off the end. A cut reply cannot be mistaken for a refusal either:
    the refusal is a complete ``{"order": []}`` and a truncation is not JSON at all.
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


def parse_order(raw: str, *, pool_size: int, k: int) -> tuple[int, ...] | None:
    """The candidate numbers the model returned: in range, de-duplicated, truncated to ``k``.

    **Three outcomes, not two** (ADR-0038 abstention addendum). ``None`` is a reply that cannot be
    used at all: not JSON, not the envelope, an ``order`` that is not a list, or a list that named
    notes of which none exists. The empty tuple is a different answer entirely, an ``order`` that
    arrived empty, which is the model saying that no candidate helps. Collapsing the two was the
    defect this signature exists to remove: the only thing a judge can do that geometry cannot is
    decline, and read as a failure it became the fallback's three irrelevant notes.

    A list that named notes and had none of them survive is a failure rather than a refusal, since
    the model tried to pick and produced nothing pickable. Individual bad elements are still
    dropped rather than voiding the answer: a model that hallucinates note 99 alongside note 2 has
    usefully ranked the rest, and refusing the whole reply over one element throws away a good
    rank. ``bool`` is an ``int`` in Python and a JSON ``true`` is not a note number, which is why
    the element check is on the exact type.
    """
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
    """Rank the candidate pool by asking the model, falling back to another policy when it cannot.

    ``candidate_k`` over-fetches ``k * pool_factor``, like the heuristic policies, so the model gets
    a pool worth judging. ``select`` sends that pool and turns the returned order into keys spread
    evenly over ``(0, 1]``, best first, on the ``VERDICT`` basis: the model gives a placing rather
    than a score, and a normalized placing is the honest reading of one.

    ``fallback`` (default the raw top-k cosine) runs whenever the model cannot be used or believed:
    an empty pool, an ``InferenceError``, a reply outside the envelope, or an order that parses to
    nothing usable. The ranking then carries the fallback's own basis, so the audit
    trail says what actually ranked rather than what was configured, which is the difference
    between an observable rank and a hopeful one. The faults among them are **logged** where they
    happen, one line for a backend that could not be asked and one for a reply no order could be
    read out of (the last two causes are that one parse outcome), because the trail is opt-in and a
    deployment whose judge has never once answered would otherwise read exactly like one where it
    answers every turn.

    **A model that picks nothing is believed, not overruled** (ADR-0038 abstention addendum). An
    ``order`` that arrives empty is the model reading the pool and answering that no candidate
    helps, which is the one judgement no geometric policy can make, so it returns an empty
    ``Ranking`` on the ``DEMUR`` basis and the fallback is never consulted. The turn then carries no
    recalled memories at all, which is what "none of these help" means; the alternative, and the
    behaviour this replaced, was handing the turn the cosine's best irrelevant notes under a basis
    that read as an unreachable model.
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
        self,
        hits: Sequence[ScoredMemory],
        *,
        query: str,
        now: datetime,
        k: int,
        session_id: str | None = None,
    ) -> Ranking:
        """Ask the model to order the pool: fall back on a failure, keep nothing on a refusal."""
        if not hits:
            # The one fallback that is not a fault: no candidates, so no judgement was possible
            # and none was attempted. Silent for the reason the summarizing window is silent when
            # its inner window dropped nothing: a line here would fire on every turn a deployment
            # recalls nothing on, and it would dilute the two below, which mean something broke.
            return await self._fallback.select(
                hits, query=query, now=now, k=k, session_id=session_id
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
            # The backend, rather than the reply: there is no completion to describe, so the
            # cause rides as ``exc_info`` the way every other degraded-turn warning carries it.
            _logger.warning(
                "the model could not be asked to rank recall; falling back to the unjudged ranking",
                extra={"session_id": session_id, "pool": len(hits), "k": k},
                exc_info=True,
            )
            return await self._fallback.select(
                hits, query=query, now=now, k=k, session_id=session_id
            )
        order = parse_order(raw, pool_size=len(hits), k=k)
        if order is None:
            # The two readings beside the message are the whole diagnosis, and they exist because
            # the reply is gone by the time anyone reads this. ``capped`` separates the two causes
            # with opposite fixes: True is ``rank_bounds`` running out mid-envelope, which wants a
            # wider bound or a smaller ``k``, and False is a model that ended by itself and wrote
            # something else. ``chars`` splits that second case again, ``0`` being a model that
            # emitted no assistant text at all and any other length being text that
            # arrived and was not the envelope, which is constrained decoding not holding. The
            # first of those is no longer a guess: this request pairs a cap with ``thinking=False``
            # AND a schema, which is the shape the switch was measured doing nothing on (ADR-0005
            # switch-is-advisory addendum), and where that happens ``drain_text`` writes its own
            # line naming the tier and the characters it dropped, so the two lines land together
            # and this one need not carry the diagnosis alone. Both
            # ride the record alone: the entry point's formatter renders whatever a record
            # carries, so spelling them into the message too would print each of them twice.
            _logger.warning(
                "the model returned no usable recall order; falling back to the unjudged ranking",
                extra={
                    "session_id": session_id,
                    "pool": len(hits),
                    "k": k,
                    "capped": stops.capped,
                    "chars": len(raw),
                },
            )
            return await self._fallback.select(
                hits, query=query, now=now, k=k, session_id=session_id
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
