from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

import pytest
import swap_harness as harness

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GenerationBounds,
    InferenceEvent,
    InMemorySessionStore,
    JsonSchema,
    Message,
    Role,
    SystemClock,
    TaintLedger,
    TextChunk,
    TextDelta,
    ToolRun,
    ToolSpec,
    TurnCapabilities,
)
from cortex_core.access_claim import UNSEARCHED_FILES_NOTE
from cortex_core.brain_phase import BrainPhase
from cortex_core.forget_count_note import forgot_count_note
from cortex_core.numbers_left_claim import NUMBERS_LEFT_NOTE
from cortex_core.schedule_claim import MONTHLY_STORED_NOTE, UNSCHEDULED_CLAIM_NOTE
from cortex_core.schedule_daily import DAILY_STORED_NOTE, DAILY_STORED_NOTES
from cortex_core.schedule_made_repeating import MADE_REPEATING_NOTE
from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME
from cortex_core.schedule_verbs import EDIT_SCHEDULED_TOOL_NAME

_AT = datetime(2026, 11, 5, 5, 0, 0, tzinfo=UTC)


class _Reply:
    def __init__(self, text: str) -> None:
        self._text = text

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
        yield TextChunk(self._text)


async def _deep_reply(
    query: str, reply: str, taint: TaintLedger, runs: tuple[ToolRun, ...] = ()
) -> str:
    sessions = InMemorySessionStore()
    await sessions.append(
        harness.SESSION, Message(role=Role.USER, text=query, at=_AT, turn_id=harness.TURN)
    )
    cortex = Message(role=Role.ASSISTANT, text="", at=_AT, turn_id=harness.TURN, runs=runs)
    await sessions.append(harness.SESSION, cortex)
    phase = BrainPhase(sessions, _Reply(reply), SystemClock(), "brain", TurnCapabilities())
    record = harness.prepared_slot(taint=taint).snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    return "".join(
        [event.text async for event in phase.run(record) if isinstance(event, TextDelta)]
    )


@pytest.mark.parametrize("stored", [True, False])
async def test_a_deep_reply_reads_a_monthly_reminder_the_cortex_stored(*, stored: bool) -> None:
    reply = "I've set a reminder for Anna's birthday every year on 11 May."
    shown = await _deep_reply(
        "Remind me of Anna's birthday on 11 May.",
        reply,
        TaintLedger(monthly_stored=stored),
        (ToolRun(SCHEDULE_TOOL_NAME, ok=True),),
    )
    assert (MONTHLY_STORED_NOTE in shown) is stored
    assert UNSCHEDULED_CLAIM_NOTE not in shown


@pytest.mark.parametrize("daily", [("abc",), ()])
async def test_a_deep_reply_reads_a_daily_reminder_the_cortex_stored(
    daily: tuple[str, ...],
) -> None:
    shown = await _deep_reply(
        "Erinnere mich um 17:30 Uhr an die Wäsche.",
        "Ich habe dich für 17:30 Uhr an die Wäsche erinnert.",
        TaintLedger(daily_stored=daily),
        (ToolRun(SCHEDULE_TOOL_NAME, ok=True),),
    )
    assert (DAILY_STORED_NOTES["de"] in shown) is bool(daily)
    assert DAILY_STORED_NOTE not in shown


@pytest.mark.parametrize("made", [("abc",), ()])
async def test_a_deep_reply_reads_a_reminder_the_cortex_made_repeat(made: tuple[str, ...]) -> None:
    shown = await _deep_reply(
        "Move my dentist reminder to Tuesday at 15:00.",
        "I've moved your dentist reminder to Tuesday at 3:00 PM.",
        TaintLedger(made_repeating=made),
        (ToolRun(EDIT_SCHEDULED_TOOL_NAME, ok=True),),
    )
    assert (MADE_REPEATING_NOTE in shown) is bool(made)


@pytest.mark.parametrize("refused", [True, False])
async def test_a_deep_reply_reads_a_file_call_the_cortex_refused(*, refused: bool) -> None:
    reply = "Noted. I don't have access to your files."
    shown = await _deep_reply(
        "Remember that my locker code is 7319.", reply, TaintLedger(sidecar_refused=refused)
    )
    assert (UNSEARCHED_FILES_NOTE in shown) is refused


@pytest.mark.parametrize("left", [True, False])
async def test_a_deep_reply_reads_a_number_the_cortex_forget_left(*, left: bool) -> None:
    shown = await _deep_reply(
        "Forget my door code.",
        "I've forgotten your door code.",
        TaintLedger(forget_asked=True, forget_calls=1, forget_numbers_left=left),
        (ToolRun(FORGET_CHOSEN_TOOL_NAME, ok=True),),
    )
    assert (NUMBERS_LEFT_NOTE in shown) is left


@pytest.mark.parametrize("deleted", [2, 0])
async def test_a_deep_reply_reads_how_many_rows_the_cortex_forget_deleted(deleted: int) -> None:
    shown = await _deep_reply(
        "Forget my door code.",
        "OK.",
        TaintLedger(forget_asked=True, forget_calls=1, forget_deleted=deleted),
        (ToolRun(FORGET_CHOSEN_TOOL_NAME, ok=True),),
    )
    assert (forgot_count_note(2, "en") in shown) is bool(deleted)
