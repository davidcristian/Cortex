"""Behavior of the model-based recall rank: what it asks, what it believes, and when it gives up.

The whole point of a judge is that it reads what a memory *says*, so the tests that matter are the
one where the model lifts a low-cosine hit that actually answers the question, and the several where
the model cannot be believed and the ranking falls back with the fallback's own basis on it.
"""

import json
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    InferenceError,
    JudgeRecallPolicy,
    MemoryRecord,
    RankBasis,
    RawRecallPolicy,
    ScoredMemory,
    TextChunk,
    ToolSpec,
)
from cortex_core.conversation import Message
from cortex_core.inference import InferenceEvent, JsonSchema
from cortex_core.rerank_judge import ORDER_ENVELOPE, build_rank_messages, parse_order

_NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def _hit(rid: str, text: str, score: float) -> ScoredMemory:
    record = MemoryRecord(id=rid, text=text, embedding=(1.0, 0.0), at=_NOW)
    return ScoredMemory(record=record, score=score)


class _ScriptedBackend:
    """An InferenceBackend that replies with one canned string, or raises."""

    def __init__(self, reply: str = "", *, error: bool = False) -> None:
        self._reply = reply
        self._error = error
        self.prompts: list[str] = []
        self.schemas: list[JsonSchema | None] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools
        self.prompts.append(messages[-1].text)
        self.schemas.append(schema)
        if self._error:
            msg = "llama-server is down"
            raise InferenceError(msg)
        yield TextChunk(self._reply)


def _pool() -> list[ScoredMemory]:
    """Three candidates whose cosine order disagrees with what actually answers the question."""
    return [
        _hit("noise", "the office coffee machine was replaced in March", 0.91),
        _hit("answer", "we decided to keep session state in Redis, never in the model", 0.62),
        _hit("stale", "a note about coffee filters", 0.75),
    ]


def _judge(reply: str = "", *, error: bool = False) -> tuple[JudgeRecallPolicy, _ScriptedBackend]:
    backend = _ScriptedBackend(reply, error=error)
    return JudgeRecallPolicy(backend, "cortex", pool_factor=4), backend


async def test_the_judge_lifts_the_answer_over_the_higher_cosine_noise() -> None:
    policy, _ = _judge(json.dumps({"order": [1, 2]}))
    ranking = await policy.select(_pool(), query="where does state live?", now=_NOW, k=2)
    assert [ranked.hit.record.id for ranked in ranking.hits] == ["answer", "stale"]
    assert ranking.basis is RankBasis.VERDICT
    assert [ranked.key for ranked in ranking.hits] == [1.0, 0.5]  # placings, normalized


async def test_the_judge_over_fetches_like_the_heuristic_policies() -> None:
    policy, _ = _judge()
    assert policy.candidate_k(5) == 20


async def test_the_judge_sends_the_question_the_numbered_notes_and_the_envelope() -> None:
    policy, backend = _judge(json.dumps({"order": [0]}))
    await policy.select(_pool(), query="where does state live?", now=_NOW, k=1)
    (prompt,) = backend.prompts
    assert "where does state live?" in prompt
    assert "0. the office coffee machine" in prompt  # candidates arrive numbered from zero
    assert "Reply with at most 1." in prompt
    assert backend.schemas == [ORDER_ENVELOPE]  # constrained decoding, never prose mining


async def test_an_unreachable_model_falls_back_and_says_so_in_the_basis() -> None:
    policy, _ = _judge(error=True)
    ranking = await policy.select(_pool(), query="where does state live?", now=_NOW, k=2)
    assert [ranked.hit.record.id for ranked in ranking.hits] == ["noise", "answer"]  # store order
    assert ranking.basis is RankBasis.ECHO  # the trail says what ranked, not what was configured


async def test_a_reply_outside_the_envelope_falls_back() -> None:
    policy, _ = _judge("I think note two is best, actually")
    ranking = await policy.select(_pool(), query="q", now=_NOW, k=2)
    assert ranking.basis is RankBasis.ECHO


async def test_an_order_of_only_junk_falls_back() -> None:
    """Every element out of range leaves nothing usable, which is the same as no answer."""
    policy, _ = _judge(json.dumps({"order": [99, -1]}))
    ranking = await policy.select(_pool(), query="q", now=_NOW, k=2)
    assert ranking.basis is RankBasis.ECHO


async def test_an_empty_pool_never_reaches_the_model() -> None:
    policy, backend = _judge()
    ranking = await policy.select([], query="q", now=_NOW, k=3)
    assert ranking.hits == ()
    assert ranking.basis is RankBasis.ECHO
    assert backend.prompts == []  # no candidates, no reason to spend a load


async def test_the_fallback_policy_is_swappable() -> None:
    policy = JudgeRecallPolicy(
        _ScriptedBackend(error=True), "cortex", pool_factor=2, fallback=RawRecallPolicy()
    )
    ranking = await policy.select(_pool(), query="q", now=_NOW, k=1)
    assert [ranked.hit.record.id for ranked in ranking.hits] == ["noise"]


def test_a_pool_factor_below_one_is_refused() -> None:
    with pytest.raises(ValueError, match="pool_factor"):
        JudgeRecallPolicy(_ScriptedBackend(), "cortex", pool_factor=0)


def test_parse_order_drops_bad_elements_without_voiding_the_answer() -> None:
    """A hallucinated note number costs that element, never the whole rank."""
    raw = json.dumps({"order": [2, 99, 2, -1, True, "1", 0]})
    assert parse_order(raw, pool_size=3, k=5) == (2, 0)  # deduped, in range, and `True` is not 1


def test_parse_order_truncates_to_k() -> None:
    assert parse_order(json.dumps({"order": [2, 1, 0]}), pool_size=3, k=2) == (2, 1)


@pytest.mark.parametrize(
    "raw",
    ["not json at all", json.dumps({"picks": [0]}), json.dumps({"order": "0,1"}), json.dumps([0])],
)
def test_parse_order_returns_empty_for_anything_unusable(raw: str) -> None:
    assert parse_order(raw, pool_size=3, k=2) == ()


def test_a_long_candidate_is_truncated_in_the_prompt() -> None:
    long_hit = _hit("long", "x" * 900, 0.5)
    (message,) = build_rank_messages("q", [long_hit], k=1, at=_NOW)
    assert "x" * 400 in message.text
    assert "x" * 401 not in message.text  # bounded, so one long memory cannot flood the prompt
