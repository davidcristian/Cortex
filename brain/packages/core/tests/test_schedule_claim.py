from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    CANCEL_SCHEDULED_TOOL_NAME,
    EDIT_SCHEDULED_TOOL_NAME,
    LIST_SCHEDULED_TOOL_NAME,
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
from cortex_core.schedule_claim import (
    LISTED_UNCHANGED_NOTE,
    LISTED_UNCHANGED_NOTES,
    UNSCHEDULED_CLAIM_NOTES,
    unscheduled_claim_note,
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
    "I've updated your plant reminder. It is now set to 9:30 every day, starting from tomorrow.",
    "I've changed your reminder to 9:30.",
    "Your reminder has been updated to 9:30.",
    "I've moved your plant reminder to 9:30.",
    "I've updated your reminders: the plant one is cancelled.",
    "Your plant reminder is ready. It is now set to 9:30.",
    "Updated your plant reminder to 9:30.",
    "I've updated your morning alarm for 7:00.",
    "Your reminder is ready. It has been moved to 9:30.",
    "I've updated your reminder time to 9:30.",
    "I've changed the alarm time to 6:30.",
    "Your reminder time has been updated to 9:30.",
    "I've updated the plant reminder message.",
    "I've moved your alarm settings to 7:00.",
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
    "I've updated your notes file.",
    "I read notes.txt. It is now set to 9:30.",
    "Should I update your reminder to 9:30?",
    "Have I updated your reminder?",
    "I haven't updated your reminder.",
    "I have not changed the reminder.",
    "Your reminder was not updated.",
    "If you want, I can change the reminder to 9:30.",
    "I've updated your phone number. You have a reminder at 9:00.",
    "It is now set to 9:30. Your reminder list is empty.",
    "I've updated your alarm code; it is now 5528.",
    "Your alarm code has been updated to 5528.",
    "I've updated your work schedule: you now start at 8.",
    "I've changed your task list in memory.",
    "I've moved your task notes to the new file.",
    "Your reminder preference is noted. It has been updated to 9 am.",
    "I've updated your alarm PIN to 4412.",
    "Your alarm system password has been changed.",
    "I've updated your alarm company's number.",
    "I've updated your reminder preferences: mornings only.",
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


_MOVE = "Move my plant reminder to 9:30."
_NOTED = "Remember that my reminder app is TickTick, update my notes about it"


@pytest.mark.parametrize(
    ("reply", "said"),
    [
        ("I've updated it to 9:30.", (_MOVE,)),
        ("I've moved it to 9:30.", (_MOVE,)),
        ("Your plant reminder is ready. I've updated it to 9:30.", ()),
        ("I've moved your 9:00 one to 9:30.", (_MOVE,)),
        ("Done, I've changed them to 9:30.", ("Move my two plant reminders to 9:30.",)),
        ("It is now set to 9:30.", (_MOVE,)),
        ("I've updated it to 9:30.", ("My alarm code is now 5528.", _MOVE)),
        ("I've updated it to 9:30 in your schedule.", (_MOVE,)),
        ("I've updated it in your schedule.", (_MOVE,)),
    ],
)
def test_an_update_of_a_pronoun_names_the_reminder_named_before_it(
    reply: str, said: tuple[str, ...]
) -> None:
    assert claims_scheduled(reply, said=said)


@pytest.mark.parametrize(
    ("reply", "said"),
    [
        ("Your alarm code is 5528. I've updated it.", ()),
        ("I've updated it.", ("My alarm code is now 5528.",)),
        ("I've updated it.", (_MOVE, "My alarm code is now 5528.")),
        ("Your phone number is 0699 000000. I've updated it.", ()),
        ("I've updated it.", ("My new phone number is 0699 000000, remember it.",)),
        ("I've moved it to the new file.", ("Move my shopping list to the new file.",)),
        ("I've moved your 9:00 one to 9:30.", ()),
        ("Should I move it to 9:30?", (_MOVE,)),
        ("Have I updated it to 9:30?", (_MOVE,)),
        ("If you like, I can move it to 9:30.", (_MOVE,)),
        ("I can update it to 9:30 once you confirm.", (_MOVE,)),
        ("I haven't moved it yet.", (_MOVE,)),
        ("I have not updated it.", (_MOVE,)),
        ("I couldn't change it to 9:30.", (_MOVE,)),
        ("I've updated it in memory.", (_NOTED,)),
        ("I've updated it in your notes.", (_NOTED,)),
        ("I've updated it in the file.", (_NOTED,)),
        ("Done, I've changed it in your long term memory.", (_NOTED,)),
    ],
)
def test_an_update_of_a_pronoun_with_no_reminder_before_it_or_no_claim_is_not_one(
    reply: str, said: tuple[str, ...]
) -> None:
    assert not claims_scheduled(reply, said=said)


@pytest.mark.parametrize(
    ("reply", "said"),
    [
        ("Done, your 9:00 reminder now goes off at 9:30.", (_MOVE,)),
        ("Your plant reminder is now at 9:30 every day.", (_MOVE,)),
        ("It now goes off at 9:30.", (_MOVE,)),
        ("Your alarm will now go off at 7:00 am.", ("Move my alarm to 7.",)),
        ("Your reminder now fires at 9:30, not 9:00.", ()),
    ],
)
def test_a_reminder_that_now_goes_off_at_a_time_is_a_claim(
    reply: str, said: tuple[str, ...]
) -> None:
    assert claims_scheduled(reply, said=said)


@pytest.mark.parametrize(
    ("reply", "said"),
    [
        ("Your reminder goes off at 9:00.", (_MOVE,)),
        ("Does your reminder now go off at 9:30?", (_MOVE,)),
        ("If you confirm, your reminder now goes off at 9:30.", (_MOVE,)),
        ("Your reminder now goes off at 9:30 if you confirm.", (_MOVE,)),
        ("I can make it so your reminder now goes off at 9:30.", (_MOVE,)),
        ("I couldn't change it, so your reminder now goes off at 9:00 as before.", (_MOVE,)),
        ("Your alarm code is now 5528.", ()),
        ("Your alarm code now rings at 9:30 on the panel.", ()),
        ("The meeting is now at 9:30.", ()),
        ("Your reminder now goes off.", (_MOVE,)),
        ("So the trigger now fires on a commit here.", ()),
        ("It now goes off at 9:30.", ("Move my meeting to 9:30.",)),
    ],
)
def test_a_new_time_asked_negated_or_naming_no_reminder_is_not_a_claim(
    reply: str, said: tuple[str, ...]
) -> None:
    assert not claims_scheduled(reply, said=said)


def test_a_new_time_after_an_edit_that_succeeded_has_no_claim_note() -> None:
    reply = "Done, your 9:00 reminder now goes off at 9:30."
    assert not unscheduled_claim((ToolRun(name=EDIT_SCHEDULED_TOOL_NAME, ok=True),), reply)
    assert unscheduled_claim((ToolRun(name="list_scheduled", ok=True),), reply, (_MOVE,))


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


def test_a_claim_after_a_list_that_succeeded_gets_the_note_asking_for_nothing_new() -> None:
    listed = ToolRun(name=LIST_SCHEDULED_TOOL_NAME, ok=True)
    assert unscheduled_claim_note((listed,), "en") == LISTED_UNCHANGED_NOTE
    assert unscheduled_claim_note((listed,), "fr") == LISTED_UNCHANGED_NOTES["fr"]
    assert "Ask" not in LISTED_UNCHANGED_NOTE


def test_a_claim_after_no_list_or_a_failed_one_gets_the_note_asking_to_schedule() -> None:
    failed = ToolRun(name=LIST_SCHEDULED_TOOL_NAME, ok=False)
    other = ToolRun(name="read_text_file", ok=True)
    assert unscheduled_claim_note((failed, other), "en") == UNSCHEDULED_CLAIM_NOTE
    assert unscheduled_claim_note((), "de") == UNSCHEDULED_CLAIM_NOTES["de"]


def test_a_claim_after_a_list_and_a_cancel_gets_the_note_asking_to_schedule() -> None:
    listed = ToolRun(name=LIST_SCHEDULED_TOOL_NAME, ok=True)
    cancelled = ToolRun(name=CANCEL_SCHEDULED_TOOL_NAME, ok=True)
    assert unscheduled_claim_note((listed, cancelled), "en") == UNSCHEDULED_CLAIM_NOTE
    refused = ToolRun(name=CANCEL_SCHEDULED_TOOL_NAME, ok=False)
    assert unscheduled_claim_note((listed, refused), "en") == LISTED_UNCHANGED_NOTE


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


async def test_a_reply_updating_the_reminder_the_message_names_gets_the_note() -> None:
    store = InMemorySessionStore()
    engine = _engine(store, [[TextChunk("I've updated it to 9:30.")]])
    events = [event async for event in engine.handle_turn("s", _MOVE, turn_id="t-1")]
    assert events[-1] == TurnCompleted(
        turn_id="t-1", full_text="I've updated it to 9:30." + UNSCHEDULED_CLAIM_NOTE
    )


async def test_a_drafted_message_in_the_person_s_voice_gets_no_note() -> None:
    store = InMemorySessionStore()
    engine = _engine(store, [[TextChunk("Hi team, I've scheduled the design review for Friday.")]])
    events = [event async for event in engine.handle_turn("s", _DRAFT_ASKED, turn_id="t-1")]
    assert events[-1] == TurnCompleted(
        turn_id="t-1", full_text="Hi team, I've scheduled the design review for Friday."
    )
