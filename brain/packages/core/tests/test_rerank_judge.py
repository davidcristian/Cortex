"""Behavior of the model-based recall rank: what it asks, what it believes, and when it gives up.

The whole point of a judge is that it reads what a memory *says*, so the tests that matter are the
one where the model lifts a low-cosine hit that actually answers the question, and the several where
the model cannot be believed and the ranking falls back with the fallback's own basis on it.

The last group is about what a fallback *says*, since the basis alone rides an opt-in trail: the
two ways a rank is lost log a line apiece and the two ways it is not log nothing, and the readings
those lines carry tell a rank the token bound cut from a model that answered in the wrong shape.
"""

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
        # What the engine said about why the completion ended, or nothing at all, which is what a
        # build that reports no reason looks like and is what this repo shipped before it could ask.
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
    """A RecallPolicy that counts how often it was asked, and under which recall's name."""

    def __init__(self) -> None:
        self.calls = 0
        self.sessions: list[str | None] = []

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
    ) -> Ranking:
        del query, now
        self.calls += 1
        self.sessions.append(session_id)
        return Ranking(
            hits=tuple(RankedMemory(hit=hit, key=hit.score) for hit in hits[:k]),
            basis=RankBasis.ECHO,
        )


def _pool() -> list[ScoredMemory]:
    """Three candidates whose cosine order disagrees with what actually answers the question."""
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
    """Every element out of range means the model tried to pick and picked nothing that exists.

    The discriminator against the abstention below: this reply named notes, so it is a failed rank
    and takes the fallback, while an empty pick names none and is believed.
    """
    policy, _ = _judge(json.dumps({"order": [99, -1]}))
    ranking = await policy.select(_pool(), query="q", now=_NOW, k=2)
    assert ranking.basis is RankBasis.ECHO


async def test_a_model_that_picks_nothing_is_believed_rather_than_overruled() -> None:
    """The one judgement no geometric policy can make: nothing here helps (ADR-0038).

    Measured on the real cortex against questions the corpus cannot answer, the reply is a
    complete `{"order": []}`. Read as a failure it became the cosine's three irrelevant notes,
    which is the defect this pins shut.
    """
    fallback = _CountingFallback()
    policy = JudgeRecallPolicy(
        _ScriptedBackend(json.dumps({"order": []})), "cortex", pool_factor=4, fallback=fallback
    )

    ranking = await policy.select(_pool(), query="what is the wifi password?", now=_NOW, k=3)

    assert ranking.hits == ()  # the turn is handed nothing, not the nearest three misses
    assert ranking.basis is RankBasis.DEMUR  # and the trail says a reader declined it
    assert fallback.calls == 0  # a refusal is an answer, so no second policy is consulted


async def test_a_declined_rank_is_not_the_same_event_as_an_unreachable_model() -> None:
    """Both hand the turn a ranking; only one of them means memory had nothing to say."""
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
    assert backend.prompts == []  # no candidates, no reason to spend a load


async def test_the_fallback_policy_is_swappable() -> None:
    policy = JudgeRecallPolicy(
        _ScriptedBackend(error=True), "cortex", pool_factor=2, fallback=RawRecallPolicy()
    )
    ranking = await policy.select(_pool(), query="q", now=_NOW, k=1)
    assert [ranked.hit.record.id for ranked in ranking.hits] == ["noise"]


async def test_every_fallback_hands_on_the_recall_it_was_given() -> None:
    """A fallback that reports would otherwise be blinded by the policy wrapping it.

    All three exits that consult a fallback forward the id: the empty pool that is no fault, the
    model that could not be asked, and the reply no order could be read out of. A judge nested
    under another judge is the case this is for, and it is the shipped fallback seam rather than a
    hypothetical, since ``fallback`` takes any ``RecallPolicy``.
    """
    fallback = _CountingFallback()
    unreachable = JudgeRecallPolicy(
        _ScriptedBackend(error=True), "cortex", pool_factor=4, fallback=fallback
    )
    unreadable = JudgeRecallPolicy(
        _ScriptedBackend("not the envelope"), "cortex", pool_factor=4, fallback=fallback
    )

    await unreachable.select(_pool(), query="q", now=_NOW, k=2, session_id="conv-9")
    await unreachable.select([], query="q", now=_NOW, k=2, session_id="conv-9")
    await unreadable.select(_pool(), query="q", now=_NOW, k=2, session_id="conv-9")

    assert fallback.sessions == ["conv-9", "conv-9", "conv-9"]


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
    [
        "not json at all",
        json.dumps({"picks": [0]}),
        json.dumps({"order": "0,1"}),
        json.dumps([0]),
        json.dumps({"order": [99, -1]}),  # it named notes; none of them exists
    ],
)
def test_parse_order_returns_none_for_anything_unusable(raw: str) -> None:
    assert parse_order(raw, pool_size=3, k=2) is None


def test_parse_order_tells_an_empty_pick_apart_from_an_unusable_reply() -> None:
    """The whole point of the three-outcome return: `[]` is an answer, not a parse failure."""
    assert parse_order(json.dumps({"order": []}), pool_size=3, k=2) == ()


async def test_the_rank_request_asks_for_no_thinking_and_room_for_k_picks() -> None:
    """The two levers ride the request, and the cap is sized from the reply the schema permits.

    Asserted together because a cap against a model that deliberates first comes back empty, and
    an empty reply here is a silent fall back to the cosine this policy exists to beat.
    """
    policy, backend = _judge(json.dumps({"order": [1]}))

    await policy.select(_pool(), query="where does state live?", now=_NOW, k=3)

    assert backend.bounds == [rank_bounds(3)]
    assert rank_bounds(3).thinking is False
    assert rank_bounds(3).max_tokens == RANK_ENVELOPE_TOKENS + 3 * RANK_TOKENS_PER_CANDIDATE


def test_the_rank_cap_grows_with_how_many_picks_were_asked_for() -> None:
    """A fixed cap would truncate the day a deployment recalls more, which is what this pins."""
    wider = rank_bounds(20).max_tokens
    narrower = rank_bounds(5).max_tokens
    assert wider is not None
    assert narrower is not None
    assert wider - narrower == 15 * RANK_TOKENS_PER_CANDIDATE


async def test_a_reply_cut_off_by_the_cap_falls_back_like_any_other_unusable_one() -> None:
    """What running into the cap degrades to: the fallback's ranking, and its basis on the trail.

    The reply is the truncated JSON a capped constrained request really returns (measured against
    the shipped cortex), so the degraded path is the one the model would take rather than a
    stand-in for it.
    """
    policy, _ = _judge('{"order":')
    ranking = await policy.select(_pool(), query="q", now=_NOW, k=2)
    assert [ranked.hit.record.id for ranked in ranking.hits] == ["noise", "answer"]
    assert ranking.basis is RankBasis.ECHO


def test_a_long_candidate_is_truncated_in_the_prompt() -> None:
    long_hit = _hit("long", "x" * 900, 0.5)
    (message,) = build_rank_messages("q", [long_hit], k=1, at=_NOW)
    assert "x" * 400 in message.text
    assert "x" * 401 not in message.text  # bounded, so one long memory cannot flood the prompt


# --- and when it does not rank, it says which way it did not ----------------------------------

# The name the module logs under, so a test can read only its own lines out of the root capture.
_JUDGE_LOGGER = "cortex_core.rerank_judge"

# One unusable reply, reused below so nothing but its cause can differ between two runs. It is the
# truncated JSON a constrained request really returns when the cap cuts it (measured against the
# shipped cortex), which is the reply a cut rank and a mangled one both arrive as.
_UNUSABLE = '{"order":'


async def _fell_back(
    caplog: pytest.LogCaptureFixture,
    *,
    reply: str = _UNUSABLE,
    error: bool = False,
    stop: StopReason | None = None,
    session_id: str | None = None,
) -> logging.LogRecord:
    """Drive one rank that falls back to geometry, and return the single warning it logged."""
    caplog.clear()
    policy, _ = _judge(reply, error=error, stop=stop)
    ranking = await policy.select(
        _pool(), query="where does state live?", now=_NOW, k=2, session_id=session_id
    )
    # The fallback itself, re-asserted here so a record about a rank that ranked could never
    # satisfy the assertions below.
    assert ranking.basis is RankBasis.ECHO
    records = [record for record in caplog.records if "unjudged ranking" in record.getMessage()]
    assert len(records) == 1
    return records[0]


def _extra(record: logging.LogRecord, field: str) -> object:
    """One structured field off a log record, ``extra`` landing in the record's own dict."""
    return record.__dict__[field]


def _own_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Only what this module logged, since the capture handler sits on the root logger."""
    return [record for record in caplog.records if record.name == _JUDGE_LOGGER]


async def test_an_unreachable_model_and_an_unreadable_reply_are_two_different_lines(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Both hand the turn the same geometric ranking; only the line says which repair to reach for.

    Before this, neither said anything at all, so a deployment whose judge had never once answered
    read exactly like one where it answers every turn.
    """
    caplog.set_level(logging.WARNING, logger=_JUDGE_LOGGER)
    unreachable = await _fell_back(caplog, error=True)
    unreadable = await _fell_back(caplog, stop=StopReason.FINISHED)

    assert unreachable.levelno == unreadable.levelno == logging.WARNING
    assert "could not be asked" in unreachable.getMessage()
    assert "no usable recall order" in unreadable.getMessage()
    # The backend's own error rides the line it caused, there being no completion to describe;
    # the unreadable reply carries no exception because nothing raised.
    assert unreachable.exc_info is not None
    assert unreadable.exc_info is None
    # Both name what was given up on: the pool that went unjudged and the width asked of it.
    assert (_extra(unreachable, "pool"), _extra(unreachable, "k")) == (3, 2)
    assert (_extra(unreadable, "pool"), _extra(unreadable, "k")) == (3, 2)


async def test_both_lines_name_the_recall_they_happened_to(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A burst of fallbacks is attributable to a conversation (ADR-0038 named-recall addendum).

    Spelled ``session`` because the recall trail spells it that way, and pairing a fallback with
    the trail line for the same recall is the whole use: on a brain serving several conversations
    the two lines are next to each other in the stream and nothing else joins them. Asserted
    against the rendered line as well as the record, since the field reaches an operator through
    the formatter and not through the record it rides on.
    """
    caplog.set_level(logging.WARNING, logger=_JUDGE_LOGGER)
    unreachable = await _fell_back(caplog, error=True, session_id="conv-7")
    unreadable = await _fell_back(caplog, stop=StopReason.FINISHED, session_id="conv-7")

    assert _extra(unreachable, "session") == _extra(unreadable, "session") == "conv-7"
    assert "session=conv-7" in PlainFormatter().format(unreachable)
    assert "session=conv-7" in PlainFormatter().format(unreadable)


async def test_a_recall_that_named_no_session_says_so_rather_than_leaving_the_field_out(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An absent field and an unnamed caller are different facts, so the line prints the second.

    Every caller the brain ships gives an id, so this is the direct caller of the port: a reader
    who saw no ``session`` at all would go looking for the deployment that dropped it.
    """
    caplog.set_level(logging.WARNING, logger=_JUDGE_LOGGER)
    record = await _fell_back(caplog, error=True)

    assert _extra(record, "session") is None
    assert "session=None" in PlainFormatter().format(record)


async def test_neither_line_carries_the_question_or_what_memory_said_about_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The identity is an id, and the two things beside it in ``select`` are conversation content.

    The pool and the ``query`` are all a policy is handed, so a line built out of either would put
    a user's question and their remembered notes into ``docker compose logs``, on the one path that
    fires when something is already wrong. This is the rule ``LoggingRecallSink`` keeps for the
    trail, kept here for the warnings beside it, and it is why the port grew a separate parameter
    rather than a wider ``query``.
    """
    caplog.set_level(logging.WARNING, logger=_JUDGE_LOGGER)
    unreachable = PlainFormatter().format(await _fell_back(caplog, error=True, session_id="conv-7"))
    unreadable = PlainFormatter().format(
        await _fell_back(caplog, stop=StopReason.FINISHED, session_id="conv-7")
    )

    for line in (unreachable, unreadable):
        assert "where does state live?" not in line  # the question the turn asked
        assert "keep session state in Redis" not in line  # and what memory had to say about it
        assert "session=conv-7" in line  # what a line may carry: the caller's own handle


async def test_a_cut_order_and_a_mangled_one_are_told_apart(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The reason the rank carries a stop ledger at all, asserted as a difference not a string.

    Both replies are byte-identical, so `parse_order` refuses both on the same rule and every
    other thing the line carries is equal. The fixes point in opposite directions: the cut one
    wants a wider `rank_bounds` or a smaller `k`, the mangled one wants the constrained decoding
    checked. Without the flag a reader has no way to choose between them.
    """
    caplog.set_level(logging.WARNING, logger=_JUDGE_LOGGER)
    cut = await _fell_back(caplog, stop=StopReason.CAPPED)
    mangled = await _fell_back(caplog, stop=StopReason.FINISHED)

    assert _extra(cut, "chars") == _extra(mangled, "chars") == len(_UNUSABLE)
    assert _extra(cut, "pool") == _extra(mangled, "pool")
    assert _extra(cut, "capped") is True
    assert _extra(mangled, "capped") is False
    # And the reading survives the handler the brain ships, which renders the record's own
    # fields onto the line: this is the exact spelling `docs/runbooks/memory-pgvector.md` sends
    # an operator to grep for, so it is asserted against the rendered line and not the record.
    assert f"capped=True chars={len(_UNUSABLE)}" in PlainFormatter().format(cut)
    assert f"capped=False chars={len(_UNUSABLE)}" in PlainFormatter().format(mangled)


async def test_a_backend_that_reports_no_reason_reads_as_uncut_rather_than_as_cut(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Silence is not a cap: a build that reports nothing must not send its reader after a token
    budget that was never the problem."""
    caplog.set_level(logging.WARNING, logger=_JUDGE_LOGGER)
    assert _extra(await _fell_back(caplog, stop=None), "capped") is False


@pytest.mark.parametrize(
    ("reply", "expected_chars"),
    [
        # A model that emitted no assistant text at all, which on this path means a tier whose
        # whole reply arrived as reasoning that `drain_text` drops unread.
        ("", 0),
        # Text arrived and was not the envelope, so constrained decoding did not hold.
        ("I think note two is best, actually", 34),
    ],
)
async def test_the_length_splits_a_silent_model_from_one_that_wrote_the_wrong_shape(
    caplog: pytest.LogCaptureFixture, reply: str, expected_chars: int
) -> None:
    """`capped` is False for both of these, so the length is the only thing that separates them.

    The number is spelled out rather than measured off the input, since an expectation computed
    the way production computes it would agree with a broken reading as readily as a working one.
    """
    caplog.set_level(logging.WARNING, logger=_JUDGE_LOGGER)
    record = await _fell_back(caplog, reply=reply, stop=StopReason.FINISHED)

    assert _extra(record, "capped") is False
    assert _extra(record, "chars") == expected_chars
    assert f"chars={expected_chars}" in PlainFormatter().format(record)


async def test_a_refusal_is_not_reported_as_a_fallback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The judge answering "none of these help" is a judgement, not a failure to reach one.

    The distinction `parse_order` draws between a failure and a refusal survives into the log by
    the refusal writing no line at all: every line from this module means the configured rank did
    not run, so a reader counting them counts faults rather than unanswerable questions. The
    refusal is on the recall trail beside a verdict, which is where a per-recall fact belongs.
    """
    caplog.set_level(logging.DEBUG, logger=_JUDGE_LOGGER)
    policy, _ = _judge(json.dumps({"order": []}))

    ranking = await policy.select(_pool(), query="what is the wifi password?", now=_NOW, k=3)

    assert ranking.basis is RankBasis.DEMUR
    assert _own_records(caplog) == []


async def test_an_empty_pool_falls_back_without_a_word(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The no-op stays quiet even at the most verbose level: nothing was asked, so nothing broke.

    It is the one fallback of the three that reports nothing, and deliberately: it would fire on
    every turn a deployment recalls nothing on, diluting the two lines that mean a rank was lost.
    """
    caplog.set_level(logging.DEBUG, logger=_JUDGE_LOGGER)
    policy, backend = _judge()

    ranking = await policy.select([], query="q", now=_NOW, k=3)

    assert (ranking.hits, backend.prompts) == ((), [])
    assert _own_records(caplog) == []
