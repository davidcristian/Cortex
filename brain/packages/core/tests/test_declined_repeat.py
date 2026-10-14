from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

from cortex_core import (
    ALREADY_DECLINED_MSG,
    ALWAYS_SALIENT,
    REDUNDANT_MSG,
    UNANSWERED_MSG,
    USER_DECLINED_MSG,
    DispatchPolicy,
    GenerationBounds,
    InferenceEvent,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    RecordingAuditSink,
    RecordingConfirmer,
    Role,
    SaliencePolicy,
    TaintLedger,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
)
from cortex_core.loop_events import StepOutcome, ToolStep
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 10, 14, 6, 0, 0, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return _AT


class _RoundsBackend:
    """Emits one scripted round of calls per step, then a plain answer."""

    def __init__(self, rounds: Sequence[Sequence[ToolCall]]) -> None:
        self._rounds = list(rounds)
        self.seen: list[Sequence[Message]] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema, bounds
        step = len(self.seen)
        self.seen.append(list(messages))
        if step >= len(self._rounds):
            yield TextChunk("done")
            return
        for call in self._rounds[step]:
            yield call


async def _sent(arguments: Mapping[str, object]) -> str:
    return f"sent:{arguments.get('to', '')}"


def _call(index: int, name: str = "send", to: str = "a@example.com") -> ToolCall:
    return ToolCall(id=f"c{index}", name=name, arguments={"to": to})


def _context(
    sink: RecordingAuditSink,
    confirmer: RecordingConfirmer,
    *,
    confirm_names: Sequence[str] = (),
    salience: SaliencePolicy | None = None,
) -> ToolLoopContext:
    """A loop over ``send`` (confirmed by its spec) and ``note`` (confirmed only by policy)."""
    registry = InMemoryToolRegistry(
        {
            "send": (ToolSpec("send", "send", {}, confirm_required=True), _sent),
            "note": (ToolSpec("note", "note", {}), _sent),
        }
    )
    policy = DispatchPolicy(confirm_names=confirm_names)
    if salience is not None:
        policy = DispatchPolicy(confirm_names=confirm_names, salience=salience)
    dispatcher = ToolDispatcher(registry, sink, _Clock(), confirmer=confirmer, policy=policy)
    return ToolLoopContext(
        dispatcher=dispatcher,
        clock=_Clock(),
        turn_id="t",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
    )


async def _run(backend: _RoundsBackend, context: ToolLoopContext) -> list[object]:
    working = [Message(role=Role.USER, text="send it", at=_AT, turn_id="t")]
    return [event async for event in stream_tool_loop(backend, "m", working, context)]


async def test_a_call_the_person_declined_is_refused_without_a_second_card() -> None:
    sink, confirmer = RecordingAuditSink(), RecordingConfirmer(answer=False)
    await _run(_RoundsBackend([[_call(1)], [_call(2)], [_call(3)]]), _context(sink, confirmer))
    assert len(confirmer.requests) == 1
    details = [record.detail for record in sink.records]
    assert details == [USER_DECLINED_MSG, ALREADY_DECLINED_MSG, ALREADY_DECLINED_MSG]


async def test_the_refused_repeat_is_neither_shown_nor_recorded_as_a_run() -> None:
    sink, confirmer = RecordingAuditSink(), RecordingConfirmer(answer=False)
    events = await _run(_RoundsBackend([[_call(1)], [_call(2)]]), _context(sink, confirmer))
    assert [event for event in events if isinstance(event, ToolStep | StepOutcome)] == [
        ToolStep(tool_name="send", summary="send"),
        StepOutcome(tool_name="send", ok=False),
    ]


async def test_the_refusal_answers_the_repeated_call_in_the_next_request() -> None:
    sink, confirmer = RecordingAuditSink(), RecordingConfirmer(answer=False)
    backend = _RoundsBackend([[_call(1)], [_call(2)]])
    await _run(backend, _context(sink, confirmer))
    answers = [message.text for message in backend.seen[-1] if message.role is Role.TOOL]
    assert len(answers) == 2
    assert ALREADY_DECLINED_MSG in answers[1]


async def test_the_same_tool_with_other_arguments_still_shows_its_card() -> None:
    sink, confirmer = RecordingAuditSink(), RecordingConfirmer(answer=False)
    rounds = [[_call(1)], [_call(2, to="b@example.com")]]
    await _run(_RoundsBackend(rounds), _context(sink, confirmer))
    assert [request.arguments for request in confirmer.requests] == [
        {"to": "a@example.com"},
        {"to": "b@example.com"},
    ]


async def test_a_declined_call_refuses_its_repeat_in_the_same_round_too() -> None:
    sink, confirmer = RecordingAuditSink(), RecordingConfirmer(answer=False)
    await _run(_RoundsBackend([[_call(1), _call(2)]]), _context(sink, confirmer))
    assert len(confirmer.requests) == 1
    assert [record.detail for record in sink.records][1] == ALREADY_DECLINED_MSG


async def test_a_tool_confirmed_only_by_the_policy_is_not_asked_twice() -> None:
    sink, confirmer = RecordingAuditSink(), RecordingConfirmer(answer=False)
    rounds = [[_call(1, name="note")], [_call(2, name="note")]]
    await _run(_RoundsBackend(rounds), _context(sink, confirmer, confirm_names=("note",)))
    assert len(confirmer.requests) == 1
    assert sink.records[-1].detail == ALREADY_DECLINED_MSG


async def test_the_decline_refuses_a_repeat_whatever_the_salience_policy() -> None:
    sink, confirmer = RecordingAuditSink(), RecordingConfirmer(answer=False)
    context = _context(sink, confirmer, salience=ALWAYS_SALIENT)
    await _run(_RoundsBackend([[_call(1)], [_call(2)], [_call(3)]]), context)
    assert len(confirmer.requests) == 1


async def test_a_card_nobody_answered_is_shown_again_for_the_next_call() -> None:
    sink, confirmer = RecordingAuditSink(), RecordingConfirmer(answer=False)
    confirmer.answer_nothing()
    await _run(_RoundsBackend([[_call(1)], [_call(2)]]), _context(sink, confirmer))
    assert len(confirmer.requests) == 2
    assert [record.detail for record in sink.records] == [UNANSWERED_MSG, UNANSWERED_MSG]


async def test_an_approved_call_repeated_is_never_answered_as_declined() -> None:
    sink, confirmer = RecordingAuditSink(), RecordingConfirmer(answer=True)
    rounds = [[_call(1)], [_call(2)], [_call(3)]]
    await _run(_RoundsBackend(rounds), _context(sink, confirmer))
    details = [record.detail for record in sink.records]
    assert details[0] == "sent:a@example.com"
    assert ALREADY_DECLINED_MSG not in details
    assert details[-1] == REDUNDANT_MSG
