from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

import pytest
from swap_harness import TickingClock

from cortex_core import (
    SCHEDULE_TOOL_NAME,
    GenerationBounds,
    InferenceEvent,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    RecordingAuditSink,
    Role,
    TaintLedger,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolRun,
    ToolSpec,
    TurnCapabilities,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.schedule_claim import MONTHLY_STORED_NOTE, claims_yearly
from cortex_core.schedule_yearly import (
    YEARLY_DATE_MSG,
    bare_days,
    monthly_for_yearly,
    names_yearly_date,
)
from cortex_core.stops import StopLedger
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 11, 5, 4, 0, 0, tzinfo=UTC)
_BIRTHDAY = "Note that my mother's birthday is on 12 May, and remind me of it the day before."
_MONTHLY = {"at_time": "09:00", "on_month_days": [11]}
_YEARLY = {"at_time": "09:00", "on_dates": ["05-11"]}


@pytest.mark.parametrize(
    "message",
    [
        _BIRTHDAY,
        "Our wedding anniversary is on 3 September. Remind me a week before.",
        "My car insurance renews every year on 20 March; remind me the day before.",
        "Her birthday is March 20th, remind me the day before",
        "Remind me of Anna's birthday on 11 May and of Tom's birthday on 3 June.",
        "The annual checkup is on 3 June; remind me a week before.",
        "The domain renewal is due Sept. 30, remind me a week before.",
        "Remind me once a year on 1 April to change the smoke alarm battery.",
    ],
)
def test_a_yearly_event_on_a_named_month_day_with_no_monthly_wording_is_a_yearly_date(
    message: str,
) -> None:
    assert names_yearly_date(message)


@pytest.mark.parametrize(
    "message",
    [
        "Remind me on the 11th of every month to pay rent.",
        "Every month on the 25th, remind me to check my bank statement.",
        "Remind me on the 11th of every month, starting in May, to pay rent",
        "the 1st of each month from March on, remind me to water the plants",
        "My phone bill is due on the 5th of each month, the first on 5 December.",
        "Pay the gym monthly, starting 1 January.",
        "Remind me every 3 months from 12 May to service the boiler.",
        "Remind me on the 11th to pay rent.",
        "Remind me in May to book the holiday.",
        "Remind me on 12/05 about the dentist.",
        "Book a table for 12 people next Friday.",
        "Remind me to pay the gas bill on the 15th, starting 15 June.",
        "Starting May 1, remind me on the 1st to pay rent.",
        "From 3 March, remind me every 4 weeks to change the water filter.",
        "remind me on the 3rd of june about the dentist",
        "The lease ends Sept. 30, remind me a week before.",
        "I'm away until June 2, so remind me on the 5th to water the plants.",
        "Her birthday is on 12 May; remind me on the 11th of each month to save for it.",
        "Pay the rent monthly from 1 May, and remind me of my birthday on 12 May.",
    ],
)
def test_monthly_wording_or_no_yearly_event_on_a_month_day_is_not_a_yearly_date(
    message: str,
) -> None:
    assert not names_yearly_date(message)


@pytest.mark.parametrize(
    ("call", "refused"),
    [
        (ToolCall(id="c", name=SCHEDULE_TOOL_NAME, arguments=_MONTHLY), True),
        (ToolCall(id="c", name=SCHEDULE_TOOL_NAME, arguments=_YEARLY), False),
        (ToolCall(id="c", name="set_volume", arguments=_MONTHLY), False),
    ],
)
def test_only_a_monthly_schedule_call_is_read_against_a_yearly_date(
    call: ToolCall, *, refused: bool
) -> None:
    assert monthly_for_yearly(call, _BIRTHDAY) is refused
    assert not monthly_for_yearly(call, "Remind me on the 11th of every month to pay rent.")


@pytest.mark.parametrize(
    ("message", "days"),
    [
        ("Remind me to pay the gas bill on the 15th, starting 15 June.", {15}),
        ("Remind me of Anna's birthday on 11 May and to pay the gas bill on the 15th.", {15}),
        ("Her birthday is March 20th, remind me the day before", set[int]()),
        ("Mum's birthday is on the 3rd of June and Tom's is May the 11th.", set[int]()),
    ],
)
def test_bare_days_are_the_ordinals_with_no_month_beside_them(message: str, days: set[int]) -> None:
    assert bare_days(message) == days


@pytest.mark.parametrize(
    ("message", "days"),
    [
        ("Remind me of Anna's birthday on 11 May and to pay rent on the first.", {1}),
        ("My lease renews on 1 January; remind me every twenty-first to pay rent.", {21}),
        ("The insurance renews on 3 March, and rent is due on the Thirty First.", {31}),
        ("Mum's birthday is on the first of June.", set[int]()),
        ("Mum's birthday is June the second.", set[int]()),
        ("Remind me first thing on 3 May about the birthday.", set[int]()),
        ("Our anniversary is on 3 May, the second one we have had.", {2}),
    ],
)
def test_bare_days_read_an_ordinal_word_after_the_or_every(message: str, days: set[int]) -> None:
    assert bare_days(message) == days


@pytest.mark.parametrize(("month_days", "refused"), [([1], False), ([11], True)])
def test_a_monthly_call_on_a_day_written_as_a_word_beside_a_birthday_runs(
    month_days: list[int], *, refused: bool
) -> None:
    query = "Remind me of Anna's birthday on 11 May and to pay rent on the first."
    arguments = {"at_time": "09:00", "on_month_days": month_days}
    call = ToolCall(id="c", name=SCHEDULE_TOOL_NAME, arguments=arguments)
    assert monthly_for_yearly(call, query) is refused


@pytest.mark.parametrize(
    ("month_days", "refused"),
    [([10], True), ([15], False), ([10, 15], False), ("15", True)],
)
def test_a_monthly_call_on_a_day_named_beside_a_birthday_is_not_read_as_yearly(
    month_days: object, *, refused: bool
) -> None:
    query = "Remind me of Anna's birthday on 11 May and to pay the gas bill on the 15th."
    arguments = {"at_time": "09:00", "on_month_days": month_days}
    call = ToolCall(id="c", name=SCHEDULE_TOOL_NAME, arguments=arguments)
    assert monthly_for_yearly(call, query) is refused


class _Backend:
    """Asks for ``calls`` in its first round and replies with text after."""

    def __init__(self, calls: Sequence[ToolCall]) -> None:
        self.seen: list[Sequence[Message]] = []
        self._calls = list(calls)

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
        self.seen.append(tuple(messages))
        calls, self._calls = self._calls, []
        for call in calls:
            yield call
        if not calls:
            yield TextChunk("done")


async def _loop(
    query: str, calls: Sequence[ToolCall], taint: TaintLedger | None = None
) -> tuple[list[object], RecordingAuditSink]:
    ran: list[object] = []
    audit = RecordingAuditSink()

    async def handler(arguments: Mapping[str, object]) -> str:
        ran.append(dict(arguments))
        return "scheduled"

    spec = ToolSpec(name=SCHEDULE_TOOL_NAME, description="s", parameters={})
    registry = InMemoryToolRegistry({SCHEDULE_TOOL_NAME: (spec, handler)})
    context = ToolLoopContext(
        dispatcher=ToolDispatcher(registry, audit, TickingClock()),
        clock=TickingClock(),
        turn_id="t",
        taint=TaintLedger() if taint is None else taint,
        nonce="n",
        session_id="s",
        query=query,
    )
    working = [Message(role=Role.USER, text=query, at=_AT, turn_id="t")]
    _ = [event async for event in stream_tool_loop(_Backend(calls), "m", working, context)]
    return ran, audit


async def test_a_monthly_call_for_a_yearly_date_is_refused_and_a_retry_on_its_days_runs() -> None:
    first = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_MONTHLY)
    again = ToolCall(id="c2", name=SCHEDULE_TOOL_NAME, arguments={**_MONTHLY, "text": "again"})
    ran, audit = await _loop(_BIRTHDAY, [first, again])
    assert ran == [{**_MONTHLY, "text": "again"}]
    refused, kept = audit.records
    assert (refused.ok, refused.detail) == (False, YEARLY_DATE_MSG)
    assert kept.ok


async def test_a_monthly_call_on_other_days_is_refused_after_one_was_refused() -> None:
    query = "Remind me of Anna's birthday on 11 May and of Tom's birthday on 3 June."
    anna = {"at_time": "09:00", "on_month_days": [10], "text": "Anna"}
    tom = {"at_time": "09:00", "on_month_days": [2], "text": "Tom"}
    calls = [
        ToolCall(id=f"c{index}", name=SCHEDULE_TOOL_NAME, arguments=arguments)
        for index, arguments in enumerate([anna, tom, tom])
    ]
    ran, audit = await _loop(query, calls)
    assert ran == [tom]
    assert [(record.ok, record.detail) for record in audit.records][:2] == [
        (False, YEARLY_DATE_MSG),
        (False, YEARLY_DATE_MSG),
    ]


@pytest.mark.parametrize(
    ("query", "arguments"),
    [
        (_BIRTHDAY, _YEARLY),
        ("Remind me to pay the gas bill on the 15th, starting 15 June.", _MONTHLY),
        ("Starting May 1, remind me on the 1st to pay rent.", _MONTHLY),
        ("Remind me on the 11th of every month, starting in May, to pay rent", _MONTHLY),
    ],
)
async def test_a_yearly_call_or_a_monthly_request_runs_at_once(
    query: str, arguments: Mapping[str, object]
) -> None:
    ran, audit = await _loop(
        query, [ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=arguments)]
    )
    assert ran == [dict(arguments)]
    assert [record.ok for record in audit.records] == [True]


@pytest.mark.parametrize(
    "reply",
    [
        "OK. I've set a reminder for you every year on March 19th at 9:00 AM.",
        "I've set a reminder for you on March 19th of every year at 9:00 AM.",
        "Done: a yearly reminder on 11 May.",
        "I'll remind you annually on 26 August.",
        "Your reminder fires once a year, on 19 March.",
    ],
)
def test_a_reply_naming_a_yearly_repeat_and_no_month_claims_yearly(reply: str) -> None:
    assert claims_yearly(reply)


@pytest.mark.parametrize(
    "reply",
    [
        "I've set a reminder on the 19th of every month at 9:00 AM.",
        "Your insurance renews every year on 20 March; I set a monthly reminder on the 19th.",
        "A reminder each month on the 11th, from 11 May. Her birthday comes every year.",
        "I've set a reminder for 19 March 2027 at 9:00 AM.",
        "I'll remind you in a year.",
        "Every 12 months on the 19th, I'll remind you.",
    ],
)
def test_a_reply_naming_months_or_no_yearly_repeat_does_not_claim_yearly(reply: str) -> None:
    assert not claims_yearly(reply)


def _closed(reply: str, *, monthly: bool) -> str:
    parts = [reply]
    taint = TaintLedger(monthly_stored=monthly)
    runs = (ToolRun(name=SCHEDULE_TOOL_NAME, ok=True),)
    list(limit_notes(StopLedger(), runs, parts, caps=TurnCapabilities(), taint=taint, query=""))
    return "".join(parts)


@pytest.mark.parametrize(
    ("reply", "monthly", "noted"),
    [
        ("OK. I've set a reminder for you every year on March 19th.", True, True),
        ("OK. I've set a reminder for you every year on March 19th.", False, False),
        ("OK. I've set a reminder on the 19th of every month.", True, False),
    ],
)
def test_a_yearly_reply_over_a_stored_monthly_rule_gets_the_note(
    reply: str, *, monthly: bool, noted: bool
) -> None:
    shown = _closed(reply, monthly=monthly)
    assert shown == reply + MONTHLY_STORED_NOTE if noted else shown == reply


@pytest.mark.parametrize(
    ("query", "arguments", "monthly"),
    [
        ("Remind me on the 11th of every month to pay rent.", _MONTHLY, True),
        (_BIRTHDAY, _YEARLY, False),
        (_BIRTHDAY, _MONTHLY, False),
    ],
)
async def test_only_a_monthly_rule_that_ran_marks_the_turn(
    query: str, arguments: Mapping[str, object], *, monthly: bool
) -> None:
    taint = TaintLedger()
    await _loop(query, [ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=arguments)], taint)
    assert taint.monthly_stored is monthly
