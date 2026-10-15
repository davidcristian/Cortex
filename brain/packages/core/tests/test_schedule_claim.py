from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    EDIT_SCHEDULED_TOOL_NAME,
    REPLY_CAPPED_NOTE,
    SCHEDULE_TOOL_NAME,
    SNOOZE_SCHEDULED_TOOL_NAME,
    UNSCHEDULED_CLAIM_NOTE,
    CompositeToolRegistry,
    DecodeStop,
    GenerationBounds,
    InferenceEvent,
    InMemoryScheduleStore,
    InMemorySessionStore,
    JsonSchema,
    Message,
    RecordingAuditSink,
    Role,
    ScheduleTaskTool,
    StopReason,
    TextChunk,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolRun,
    ToolSpec,
    TurnCapabilities,
    TurnCompleted,
    TurnEngine,
    claims_scheduled,
    said_by_person,
    unscheduled_claim,
)

_START = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)

CLAIMS = [
    "I have scheduled a background task for tomorrow",
    "OK. I've scheduled a reminder for you to check the order at 10:00 AM.",
    "Done. I\u2019ve scheduled a background task for you.",
    "I scheduled it for 10:00.",
    "I have now scheduled the check for tomorrow.",
    "I have set it as a reminder instead.",
    "OK. I've set a reminder for you tomorrow, October 12th, at 10:00 AM.",
    "I've also created a task that checks the order.",
    "I added a reminder to your schedule.",
    "I've just booked an alarm for 7:00.",
    "The check has been scheduled for tomorrow.",
    "Your reminders have been set.",
    "The background task is now scheduled.",
    "Your reminder has been successfully added.",
    "I have scheduled it for 10:00. Is there anything else?",
]

NOT_CLAIMS = [
    "",
    "I'll now schedule a background task for tomorrow at 10:00.",
    "I can still set a reminder for you if you would like.",
    "Shall I set a reminder for 10:00 instead?",
    "The task was not scheduled.",
    "I have not scheduled anything.",
    "I haven't set a reminder.",
    "I've not set the reminder yet.",
    "You have a reminder scheduled for 9:00 to call Ana.",
    "Your reminder to call Ana is scheduled for tomorrow at 9:00.",
    "The task has not been scheduled.",
    "I have rescheduled nothing.",
    "I've set out what the file says.",
    "I've created a summary of the notes.",
    "I set the table.",
    "I've set out the notes. The reminder was not set.",
    "The schedule lists eight items, and I have read the file.",
]


@pytest.mark.parametrize("reply", CLAIMS)
def test_a_reply_saying_something_was_scheduled_is_a_claim(reply: str) -> None:
    assert claims_scheduled(reply)


@pytest.mark.parametrize("reply", NOT_CLAIMS)
def test_a_reply_that_offers_negates_or_describes_is_not_a_claim(reply: str) -> None:
    assert not claims_scheduled(reply)


def test_a_claim_after_a_question_in_the_same_reply_is_still_found() -> None:
    assert claims_scheduled("Did you mean 10:00? I have scheduled it for 10:00.")


def test_a_claim_on_a_later_line_is_found() -> None:
    assert claims_scheduled("The file lists four items\nI've set a reminder for tomorrow")


_DRAFT_ASKED = (
    "Write a one-line message I can send to my team saying that I have scheduled the design "
    "review for Friday at 10."
)
_ANA = "I have scheduled a call with Ana on Friday at 15:00. Set a reminder for an hour before it."
_CHAIN = (
    "What does meeting-notes.txt in my files say?",
    "Set a reminder for tomorrow at 9:00 to call Ana about the bulb payments.",
    "Read meeting-notes.txt again, then schedule a background task for tomorrow at 10:00 that "
    "checks whether the bulb order went out.",
)


@pytest.mark.parametrize(
    ("reply", "said"),
    [
        ("Hi team, I've scheduled the design review for Friday at 10:00 AM.", (_DRAFT_ASKED,)),
        (
            "Please note that the design review has been scheduled for Friday at 10:00 AM.",
            (_DRAFT_ASKED, "Thanks. Make it a little more formal."),
        ),
        ("Hi Sam,\n\nI've scheduled our one-to-one for Tuesday at 15:00.", (_DRAFT_ASKED,)),
    ],
)
def test_a_message_drafted_in_the_person_s_voice_repeats_their_claim(
    reply: str, said: tuple[str, ...]
) -> None:
    assert not claims_scheduled(reply, said=said)


@pytest.mark.parametrize(
    ("reply", "said"),
    [
        ("I've set a reminder for Friday at 14:00, an hour before your call with Ana.", (_ANA,)),
        ("I've scheduled a reminder for 14:00 on Friday.", (_ANA,)),
        ("Your reminder has been scheduled for 14:00.", (_ANA,)),
        ("I scheduled it for 10:00.", ("Schedule the design review for Friday at 10.",)),
        ("I scheduled it for 10:00.", ("Have I scheduled the design review?",)),
        *((claim, _CHAIN) for claim in CLAIMS[:7]),
    ],
)
def test_a_claim_is_kept_when_it_names_a_reminder_or_the_person_claimed_nothing(
    reply: str, said: tuple[str, ...]
) -> None:
    assert claims_scheduled(reply, said=said)


def test_only_the_person_s_own_messages_are_what_they_said() -> None:
    history = [
        Message(role=Role.USER, text=_DRAFT_ASKED, at=_START, turn_id="t-1"),
        Message(role=Role.ASSISTANT, text="I have scheduled it.", at=_START, turn_id="t-1"),
        Message(role=Role.USER, text="Shorter.", at=_START, turn_id="t-2"),
    ]
    assert said_by_person(history) == (_DRAFT_ASKED, "Shorter.")


@pytest.mark.parametrize(
    "name", [SCHEDULE_TOOL_NAME, EDIT_SCHEDULED_TOOL_NAME, SNOOZE_SCHEDULED_TOOL_NAME]
)
def test_a_scheduling_call_that_succeeded_clears_the_claim(name: str) -> None:
    runs = (ToolRun(name="read_text_file", ok=True), ToolRun(name=name, ok=True))
    assert not unscheduled_claim(runs, "I've scheduled it.")


def test_a_refused_scheduling_call_or_another_tool_leaves_the_claim() -> None:
    runs = (
        ToolRun(name=SCHEDULE_TOOL_NAME, ok=False),
        ToolRun(name="list_scheduled", ok=True),
    )
    assert unscheduled_claim(runs, "I have set it as a reminder instead.")
    assert not unscheduled_claim(runs, "It was not scheduled.")


class _Clock:
    def __init__(self) -> None:
        self._ticks = 0

    def now(self) -> datetime:
        self._ticks += 1
        return _START + timedelta(seconds=self._ticks)


class _Scripted:
    def __init__(self, steps: Sequence[Sequence[InferenceEvent]]) -> None:
        self._steps = list(steps)

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        for event in self._steps.pop(0):
            yield event


def _engine(store: InMemorySessionStore, steps: Sequence[Sequence[InferenceEvent]]) -> TurnEngine:
    tool = ScheduleTaskTool(InMemoryScheduleStore(), _Clock(), tasks_enabled=False, max_active=8)
    dispatcher = ToolDispatcher(CompositeToolRegistry([tool]), RecordingAuditSink(), _Clock())
    return TurnEngine(
        store, _Scripted(steps), _Clock(), capabilities=TurnCapabilities(tools=dispatcher)
    )


async def _reply(engine: TurnEngine) -> tuple[str, str]:
    events = [event async for event in engine.handle_turn("s", "go", turn_id="t-1")]
    shown = "".join(event.text for event in events if isinstance(event, TextDelta))
    completed = events[-1]
    assert isinstance(completed, TurnCompleted)
    assert completed.full_text == shown
    return shown, completed.full_text


async def test_a_turn_that_claims_with_no_call_ends_with_the_note_it_stores() -> None:
    store = InMemorySessionStore()
    claim = "I've scheduled a background task for you."
    shown, _ = await _reply(_engine(store, [[TextChunk(claim)]]))
    assert shown == claim + UNSCHEDULED_CLAIM_NOTE
    assert (await store.history("s"))[-1].text == shown


async def test_a_claim_after_a_refused_call_gets_the_note() -> None:
    store = InMemorySessionStore()
    refused = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments={"kind": "task"})
    claim = "I have set it as a reminder instead."
    shown, _ = await _reply(_engine(store, [[refused], [TextChunk(claim)]]))
    assert shown == claim + UNSCHEDULED_CLAIM_NOTE


async def test_a_claim_after_a_call_that_succeeded_gets_no_note() -> None:
    store = InMemorySessionStore()
    call = ToolCall(
        id="c1",
        name=SCHEDULE_TOOL_NAME,
        arguments={"kind": "reminder", "text": "stretch", "in_seconds": 60},
    )
    claim = "I've set a reminder for you."
    shown, _ = await _reply(_engine(store, [[call], [TextChunk(claim)]]))
    assert shown == claim


async def test_the_note_comes_after_the_length_note() -> None:
    store = InMemorySessionStore()
    capped = [TextChunk("I've scheduled the task"), DecodeStop(StopReason.CAPPED)]
    shown, _ = await _reply(_engine(store, [capped]))
    assert shown == "I've scheduled the task" + REPLY_CAPPED_NOTE + UNSCHEDULED_CLAIM_NOTE


async def test_a_reply_with_no_claim_gets_no_note() -> None:
    store = InMemorySessionStore()
    shown, _ = await _reply(_engine(store, [[TextChunk("It was not scheduled.")]]))
    assert shown == "It was not scheduled."


async def test_a_drafted_message_in_the_person_s_voice_gets_no_note() -> None:
    store = InMemorySessionStore()
    engine = _engine(store, [[TextChunk("Hi team, I've scheduled the design review for Friday.")]])
    events = [event async for event in engine.handle_turn("s", _DRAFT_ASKED, turn_id="t-1")]
    assert events[-1] == TurnCompleted(
        turn_id="t-1", full_text="Hi team, I've scheduled the design review for Friday."
    )
