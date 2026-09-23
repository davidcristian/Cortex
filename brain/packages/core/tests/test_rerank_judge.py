import json
import logging
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    InferenceError,
    JudgeRecallPolicy,
    MemoryRecord,
    PlainFormatter,
    RankBasis,
    RankedMemory,
    Ranking,
    RawRecallPolicy,
    ScoredMemory,
    TextChunk,
    ToolSpec,
)
from cortex_core.conversation import Message
from cortex_core.inference import (
    DecodeStop,
    GenerationBounds,
    InferenceEvent,
    JsonSchema,
    StopReason,
)
from cortex_core.rerank_judge import (
    ORDER_ENVELOPE,
    RANK_ENVELOPE_TOKENS,
    RANK_TOKENS_PER_CANDIDATE,
    build_rank_messages,
    parse_order,
    rank_bounds,
)

_NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def _hit(rid: str, text: str, score: float) -> ScoredMemory:
    record = MemoryRecord(id=rid, text=text, embedding=(1.0, 0.0), at=_NOW)
    return ScoredMemory(record=record, score=score)


class _ScriptedBackend:
    """An InferenceBackend that replies with one canned string, or raises."""

    def __init__(
        self, reply: str = "", *, error: bool = False, stop: StopReason | None = None
    ) -> None:
        self._reply = reply
        self._error = error
        self._stop = stop
        self.prompts: list[str] = []
        self.schemas: list[JsonSchema | None] = []
        self.bounds: list[GenerationBounds | None] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools
        self.prompts.append(messages[-1].text)
        self.schemas.append(schema)
        self.bounds.append(bounds)
        if self._error:
            msg = "llama-server is down"
            raise InferenceError(msg)
        yield TextChunk(self._reply)
        if self._stop is not None:
            yield DecodeStop(reason=self._stop)


class _CountingFallback:
    """A RecallPolicy that counts how often it was asked, and for which recall."""

    def __init__(self) -> None:
        self.calls = 0
        self.sessions: list[str | None] = []
        self.turns: list[str | None] = []

    def candidate_k(self, k: int) -> int:
        return k

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
        del query, now
        self.calls += 1
        self.sessions.append(session_id)
        self.turns.append(turn_id)
        return Ranking(
            hits=tuple(RankedMemory(hit=hit, key=hit.score) for hit in hits[:k]),
            basis=RankBasis.ECHO,
        )


def _pool() -> list[ScoredMemory]:
    """Three candidates whose similarity order differs from the one that answers the question."""
    return [
        _hit("noise", "the office coffee machine was replaced in March", 0.91),
        _hit("answer", "we decided to keep session state in Redis, never in the model", 0.62),
        _hit("stale", "a note about coffee filters", 0.75),
    ]


def _judge(
    reply: str = "", *, error: bool = False, stop: StopReason | None = None
) -> tuple[JudgeRecallPolicy, _ScriptedBackend]:
    backend = _ScriptedBackend(reply, error=error, stop=stop)
    return JudgeRecallPolicy(backend, "cortex", pool_factor=4), backend


async def test_the_judge_lifts_the_answer_over_the_higher_cosine_noise() -> None:
    policy, _ = _judge(json.dumps({"order": [1, 2]}))
    ranking = await policy.select(_pool(), query="where does state live?", now=_NOW, k=2)
    assert [ranked.hit.record.id for ranked in ranking.hits] == ["answer", "stale"]
    assert ranking.basis is RankBasis.VERDICT
    assert [ranked.key for ranked in ranking.hits] == [1.0, 0.5]


async def test_the_judge_sends_the_question_the_numbered_notes_and_the_envelope() -> None:
    policy, backend = _judge(json.dumps({"order": [0]}))
    await policy.select(_pool(), query="where does state live?", now=_NOW, k=1)
    (prompt,) = backend.prompts
    assert "where does state live?" in prompt
    assert "0. the office coffee machine" in prompt
    assert "Reply with at most 1." in prompt
    assert backend.schemas == [ORDER_ENVELOPE]


async def test_an_unreachable_model_falls_back_and_says_so_in_the_basis() -> None:
    policy, _ = _judge(error=True)
    ranking = await policy.select(_pool(), query="where does state live?", now=_NOW, k=2)
    assert [ranked.hit.record.id for ranked in ranking.hits] == ["noise", "answer"]
    assert ranking.basis is RankBasis.ECHO


async def test_a_reply_outside_the_envelope_falls_back() -> None:
    policy, _ = _judge("I think note two is best, actually")
    ranking = await policy.select(_pool(), query="q", now=_NOW, k=2)
    assert ranking.basis is RankBasis.ECHO


async def test_an_order_of_only_junk_falls_back() -> None:
    policy, _ = _judge(json.dumps({"order": [99, -1]}))
    ranking = await policy.select(_pool(), query="q", now=_NOW, k=2)
    assert ranking.basis is RankBasis.ECHO


async def test_a_model_that_picks_nothing_is_believed_rather_than_overruled() -> None:
    fallback = _CountingFallback()
    policy = JudgeRecallPolicy(
        _ScriptedBackend(json.dumps({"order": []})), "cortex", pool_factor=4, fallback=fallback
    )

    ranking = await policy.select(_pool(), query="what is the wifi password?", now=_NOW, k=3)

    assert ranking.hits == ()
    assert ranking.basis is RankBasis.DEMUR
    assert fallback.calls == 0


async def test_a_declined_rank_is_not_the_same_event_as_an_unreachable_model() -> None:
    declined, _ = _judge(json.dumps({"order": []}))
    unreachable, _ = _judge(error=True)

    refusal = await declined.select(_pool(), query="q", now=_NOW, k=3)
    failure = await unreachable.select(_pool(), query="q", now=_NOW, k=3)

    assert (refusal.basis, len(refusal.hits)) == (RankBasis.DEMUR, 0)
    assert (failure.basis, len(failure.hits)) == (RankBasis.ECHO, 3)


async def test_an_empty_pool_never_reaches_the_model() -> None:
    policy, backend = _judge()
    ranking = await policy.select([], query="q", now=_NOW, k=3)
    assert ranking.hits == ()
    assert ranking.basis is RankBasis.ECHO
    assert backend.prompts == []


async def test_the_fallback_policy_is_swappable() -> None:
    policy = JudgeRecallPolicy(
        _ScriptedBackend(error=True), "cortex", pool_factor=2, fallback=RawRecallPolicy()
    )
    ranking = await policy.select(_pool(), query="q", now=_NOW, k=1)
    assert [ranked.hit.record.id for ranked in ranking.hits] == ["noise"]


async def test_every_fallback_hands_on_the_recall_it_was_given() -> None:
    fallback = _CountingFallback()
    unreachable = JudgeRecallPolicy(
        _ScriptedBackend(error=True), "cortex", pool_factor=4, fallback=fallback
    )
    unreadable = JudgeRecallPolicy(
        _ScriptedBackend("not the envelope"), "cortex", pool_factor=4, fallback=fallback
    )

    for policy, pool in ((unreachable, _pool()), (unreachable, []), (unreadable, _pool())):
        await policy.select(pool, query="q", now=_NOW, k=2, session_id="conv-9", turn_id="turn-4")

    assert fallback.sessions == ["conv-9", "conv-9", "conv-9"]
    assert fallback.turns == ["turn-4", "turn-4", "turn-4"]


def test_parse_order_drops_bad_elements_without_voiding_the_answer() -> None:
    raw = json.dumps({"order": [2, 99, 2, -1, True, "1", 0]})
    assert parse_order(raw, pool_size=3, k=5) == (2, 0)


def test_parse_order_truncates_to_k() -> None:
    assert parse_order(json.dumps({"order": [2, 1, 0]}), pool_size=3, k=2) == (2, 1)


@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",
        json.dumps({"picks": [0]}),
        json.dumps({"order": "0,1"}),
        json.dumps([0]),
        json.dumps({"order": [99, -1]}),
    ],
)
def test_parse_order_returns_none_for_anything_unusable(raw: str) -> None:
    assert parse_order(raw, pool_size=3, k=2) is None


def test_parse_order_tells_an_empty_pick_apart_from_an_unusable_reply() -> None:
    assert parse_order(json.dumps({"order": []}), pool_size=3, k=2) == ()


async def test_the_rank_request_asks_for_no_thinking_and_room_for_k_picks() -> None:
    policy, backend = _judge(json.dumps({"order": [1]}))

    await policy.select(_pool(), query="where does state live?", now=_NOW, k=3)

    assert backend.bounds == [rank_bounds(3)]
    assert rank_bounds(3).thinking is False
    assert rank_bounds(3).trace_tokens == 0
    assert rank_bounds(3).max_tokens == RANK_ENVELOPE_TOKENS + 3 * RANK_TOKENS_PER_CANDIDATE


def test_the_rank_cap_grows_with_how_many_picks_were_asked_for() -> None:
    wider = rank_bounds(20).max_tokens
    narrower = rank_bounds(5).max_tokens
    assert wider is not None
    assert narrower is not None
    assert wider - narrower == 15 * RANK_TOKENS_PER_CANDIDATE


async def test_a_reply_cut_off_by_the_cap_falls_back_like_any_other_unusable_one() -> None:
    policy, _ = _judge('{"order":')
    ranking = await policy.select(_pool(), query="q", now=_NOW, k=2)
    assert [ranked.hit.record.id for ranked in ranking.hits] == ["noise", "answer"]
    assert ranking.basis is RankBasis.ECHO


def test_a_long_candidate_is_truncated_in_the_prompt() -> None:
    long_hit = _hit("long", "x" * 900, 0.5)
    (message,) = build_rank_messages("q", [long_hit], k=1, at=_NOW)
    assert "x" * 400 in message.text
    assert "x" * 401 not in message.text


_JUDGE_LOGGER = "cortex_core.rerank_judge"

# The truncated JSON a constrained request returns when the cap cuts it, measured against the
# shipped cortex. A cut reply and a mangled one both arrive in this form.
_UNUSABLE = '{"order":'


async def _fell_back(
    caplog: pytest.LogCaptureFixture,
    *,
    reply: str = _UNUSABLE,
    error: bool = False,
    stop: StopReason | None = None,
    session_id: str | None = None,
    turn_id: str | None = None,
) -> logging.LogRecord:
    """Run one rank that falls back to similarity, and return the warning it logged."""
    caplog.clear()
    policy, _ = _judge(reply, error=error, stop=stop)
    ranking = await policy.select(
        _pool(),
        query="where does state live?",
        now=_NOW,
        k=2,
        session_id=session_id,
        turn_id=turn_id,
    )
    assert ranking.basis is RankBasis.ECHO
    records = [record for record in caplog.records if "unjudged ranking" in record.getMessage()]
    assert len(records) == 1
    return records[0]


def _extra(record: logging.LogRecord, field: str) -> object:
    """One structured field of a log record, which ``extra=`` puts in the record's own dict."""
    return record.__dict__[field]


def _own_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Only the records this module logged, since the capture handler is on the root logger."""
    return [record for record in caplog.records if record.name == _JUDGE_LOGGER]


async def test_an_unreachable_model_and_an_unreadable_reply_are_two_different_lines(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_JUDGE_LOGGER)
    unreachable = await _fell_back(caplog, error=True)
    unreadable = await _fell_back(caplog, stop=StopReason.FINISHED)

    assert unreachable.levelno == unreadable.levelno == logging.WARNING
    assert "could not be asked" in unreachable.getMessage()
    assert "no usable recall order" in unreadable.getMessage()
    assert unreachable.exc_info is not None
    assert unreadable.exc_info is None
    assert (_extra(unreachable, "pool"), _extra(unreachable, "k")) == (3, 2)
    assert (_extra(unreadable, "pool"), _extra(unreadable, "k")) == (3, 2)


async def test_both_lines_name_the_recall_they_happened_to(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_JUDGE_LOGGER)
    unreachable = await _fell_back(caplog, error=True, session_id="conv-7", turn_id="turn-3")
    unreadable = await _fell_back(
        caplog, stop=StopReason.FINISHED, session_id="conv-7", turn_id="turn-3"
    )

    for field, value in (("session_id", "conv-7"), ("turn_id", "turn-3")):
        assert _extra(unreachable, field) == _extra(unreadable, field) == value
        assert f"{field}={value}" in PlainFormatter().format(unreachable)
        assert f"{field}={value}" in PlainFormatter().format(unreadable)


async def test_a_recall_that_named_no_session_says_so_rather_than_leaving_the_field_out(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_JUDGE_LOGGER)
    record = await _fell_back(caplog, error=True)

    for field in ("session_id", "turn_id"):
        assert _extra(record, field) is None
        assert f"{field}=None" in PlainFormatter().format(record)


async def test_neither_line_contains_the_question_or_what_memory_said_about_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_JUDGE_LOGGER)
    unreachable = PlainFormatter().format(await _fell_back(caplog, error=True, session_id="conv-7"))
    unreadable = PlainFormatter().format(
        await _fell_back(caplog, stop=StopReason.FINISHED, session_id="conv-7")
    )

    for line in (unreachable, unreadable):
        assert "where does state live?" not in line
        assert "keep session state in Redis" not in line
        assert "session_id=conv-7" in line


async def test_a_cut_order_and_a_mangled_one_are_told_apart(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_JUDGE_LOGGER)
    cut = await _fell_back(caplog, stop=StopReason.CAPPED)
    mangled = await _fell_back(caplog, stop=StopReason.FINISHED)

    assert _extra(cut, "chars") == _extra(mangled, "chars") == len(_UNUSABLE)
    assert _extra(cut, "pool") == _extra(mangled, "pool")
    assert _extra(cut, "capped") is True
    assert _extra(mangled, "capped") is False
    assert f"capped=True chars={len(_UNUSABLE)}" in PlainFormatter().format(cut)
    assert f"capped=False chars={len(_UNUSABLE)}" in PlainFormatter().format(mangled)


async def test_a_backend_that_reports_no_reason_reads_as_uncut_rather_than_as_cut(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_JUDGE_LOGGER)
    assert _extra(await _fell_back(caplog, stop=None), "capped") is False


@pytest.mark.parametrize(
    ("reply", "expected_chars"),
    [
        ("", 0),
        ("I think note two is best, actually", 34),
    ],
)
async def test_the_length_splits_a_silent_model_from_one_that_wrote_the_wrong_shape(
    caplog: pytest.LogCaptureFixture, reply: str, expected_chars: int
) -> None:
    caplog.set_level(logging.WARNING, logger=_JUDGE_LOGGER)
    record = await _fell_back(caplog, reply=reply, stop=StopReason.FINISHED)

    assert _extra(record, "capped") is False
    assert _extra(record, "chars") == expected_chars
    assert f"chars={expected_chars}" in PlainFormatter().format(record)


async def test_a_refusal_is_not_reported_as_a_fallback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_JUDGE_LOGGER)
    policy, _ = _judge(json.dumps({"order": []}))

    ranking = await policy.select(_pool(), query="what is the wifi password?", now=_NOW, k=3)

    assert ranking.basis is RankBasis.DEMUR
    assert _own_records(caplog) == []


async def test_an_empty_pool_falls_back_without_a_word(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_JUDGE_LOGGER)
    policy, backend = _judge()

    ranking = await policy.select([], query="q", now=_NOW, k=3)

    assert (ranking.hits, backend.prompts) == ((), [])
    assert _own_records(caplog) == []
