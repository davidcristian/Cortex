from collections.abc import Mapping
from datetime import UTC, datetime

import pytest
from swap_harness import ScriptedBrainBackend, TickingClock

from cortex_core import (
    SCHEDULE_TOOL_NAME,
    InMemoryScheduleStore,
    InMemoryToolRegistry,
    Message,
    RecordingAuditSink,
    Role,
    ScheduleTaskTool,
    TaintLedger,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolRun,
    ToolSpec,
    TurnCapabilities,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.schedule_daily import DAILY_STORED_NOTE, daily_after, names_repeat
from cortex_core.schedule_tools import DAILY_NOTE
from cortex_core.schedule_verbs import CANCEL_SCHEDULED_TOOL_NAME, EDIT_SCHEDULED_TOOL_NAME
from cortex_core.stops import StopLedger
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 11, 7, 4, 0, 0, tzinfo=UTC)
_WASH = "Erinnere mich um 17:30 Uhr an die Wäsche."
_DAILY = f"scheduled reminder abc: due 2026-11-07T17:30:00+01:00 (today), every day{DAILY_NOTE}"
_HELD = (
    "already scheduled reminder abc: due 2026-11-07T17:30:00+01:00 (today), every day; it was on "
    f"the schedule before this call, so no copy was added{DAILY_NOTE}"
)
_ONCE = "scheduled reminder abc: due 2026-11-07T17:30:00+01:00 (today)"
_WEEKLY = "scheduled reminder abc: due 2026-11-09T17:30:00+01:00 (Monday), every mon"


@pytest.mark.parametrize(
    "reply",
    [
        "I've set a reminder for 17:30 every day.",
        "This reminder repeats daily at 17:30.",
        "It repeats each morning at 9.",
        "Ich erinnere dich jeden Tag um 17:30 Uhr an die Wäsche.",
        "Die Erinnerung wird täglich um 17:30 Uhr wiederholt.",
        "Je te rappellerai tous les jours à 17h30 d'appeler le plombier.",
        "Ce rappel se répète chaque jour à 17h30.",
        "Un rappel quotidien est prévu à 17h30.",
        "Te lo recordaré todos los días a las 17:30.",
        "El recordatorio se repite cada día a las 17:30.",
        "Îți voi aminti în fiecare zi la 17:30 să suni instalatorul.",
        "Mementoul este zilnic, la ora 17:30.",
        "Je te le rappellerai tous les jours à 8h.",
        "Ich erinnere dich täglich um 8 Uhr.",
        "Ich erinnere dich jeden Morgen um 8 Uhr.",
        "Je te le rappellerai chaque matin à 8h.",
        "Te lo recordaré cada mañana a las 8.",
        "Te lo recordaré cada noche a las 8.",
        "Te lo recordaré diariamente a las 8.",
        "Îți voi aminti zi de zi la 8.",
        "It's a recurring reminder at 8:00.",
        "Done. It's repeating at 8:00, and I set it for the kitchen.",
        "No problem, I'll remind you every day at 8.",
        "I'll remind you every day at 8; no need to ask again.",
        "Ich erinnere dich jeden Tag um 8 Uhr, vergiss es nicht.",
        "(Note: This reminder is currently set to repeat every day.)",
        "Diese Erinnerung wiederholt sich täglich. Wenn du sie nur einmal willst, sag es mir.",
        "I'll remind you every day at 8 so you can take your pills.",
        "Done: a daily reminder at 8, like you asked.",
        "I'll remind you every day at 8 so you don't forget your pills.",
        "Je te le rappellerai tous les jours à 8h pour que tu n'oublies pas.",
        "Te lo recordaré cada día a las 8 para que no lo olvides.",
        "Îți voi aminti zilnic la 8 ca să nu uiți.",
        "Ich erinnere dich täglich um 8, damit du es nicht vergessen kannst.",
        "I've set a daily reminder for 8:00.",
        "Ich habe bereits einen täglichen Reminder für „Wäsche“ um 17:30 Uhr eingerichtet.",
        "Your daily 8:00 reminder is set.",
        "I'll remind you daily at 8.",
        "Je te le rappellerai quotidiennement à 8h.",
        "Te lo recordaré a diario a las 8.",
        "Tienes un recordatorio diario a las 8.",
        "I'll remind you at 8 every morning.",
        "I'll remind you at 8 every morning to take your pill.",
        "You will get a reminder at 8 every morning.",
        "Done, you will get a reminder every morning at 8.",
        "Ich erinnere dich um 8 Uhr jeden Morgen an die Tablette.",
        "Je te le rappellerai à 8h chaque matin.",
        "Te lo recordaré a las 8 cada mañana.",
        "Îți voi aminti la 8 în fiecare dimineață.",
        "Te lo recordaré a las 8. (Ten en cuenta que esto se repetirá todos los días).",
        "Note que ce rappel se répète chaque jour.",
        "Am setat un memento care se repetă în fiecare zi.",
    ],
)
def test_a_reply_that_says_it_repeats_names_a_repeat(reply: str) -> None:
    assert names_repeat(reply)


@pytest.mark.parametrize(
    "reply",
    [
        "I'll remind you at 17:30 to call the plumber.",
        "I'll remind you today at 17:30.",
        "I'll remind you at 17:30, every time you ask.",
        "This reminder does not repeat.",
        "It won't repeat.",
        "It will not be repeated.",
        "Ich habe dich für 17:30 Uhr an die Wäsche erinnert.",
        "Ich erinnere dich heute um 17:30 Uhr an die Wäsche.",
        "Die Erinnerung wiederholt sich nicht.",
        "Je te rappellerai aujourd'hui à 17h30.",
        "Ce rappel ne se répète pas.",
        "Te lo recordaré hoy a las 17:30.",
        "El recordatorio no se repite.",
        "Îți voi aminti azi la 17:30.",
        "Mementoul nu se repetă.",
        "I'll remind you at 8 am. This won't repeat.",
        "Set for 8:00. It does not repeat.",
        "Your reminder at 8 every weekday is set.",
        "I'll remind you at 8 tomorrow. Repeat after me: water the plants.",
        "It will repeat the question at 8.",
        "Reminder set for 8:00. If you want it every day, tell me.",
        "I'll remind you once at 8. Should it repeat?",
        "I'll remind you at 8 tomorrow; I can repeat this if you want.",
        "Te lo recordaré mañana a las 8. ¿Quieres que se repita cada día?",
        "If you like, I'll remind you every day at 8.",
        "I'll remind you every day at 8 if you want.",
        "I can make it repeat every day.",
        "Would you like this every day",
        "I'll remind you tomorrow at 8, not every day.",
        "I won't remind you every day, only tomorrow.",
        "Je peux te le rappeler tous les jours.",
        "Si tu veux, je te le rappellerai chaque jour.",
        "Ce rappel n'est pas quotidien.",
        "Wenn du willst, erinnere ich dich jeden Tag um 8 Uhr.",
        "Ich kann dich täglich erinnern.",
        "Soll ich dich jeden Tag erinnern",
        "Puedo recordártelo todos los días.",
        "Si quieres, te lo recuerdo cada día.",
        "Dacă vrei, îți amintesc în fiecare zi.",
        "Pot să îți amintesc zilnic.",
        "Do you need this every day?",
        "¿Te lo recuerdo todos los días?",
        "If needed, I'll remind you every day at 8.",
        "Si besoin, je te le rappellerai tous les jours.",
        "Wenn nötig, erinnere ich dich jeden Tag.",
        "Falls nötig, erinnere ich dich jeden Tag.",
        "Si hace falta, te lo recuerdo cada día.",
        "Dacă e nevoie, îți amintesc în fiecare zi.",
        "I can remind you every day at 8 so you don't forget.",
        "I'll remind you every day at 8 so you don't forget, if you want.",
        "I'll remind you at 8 so you don't forget to take them every day.",
        "Would you like a daily reminder at 8 so you can take your pills?",
        "Je peux te le rappeler tous les jours pour que tu n'oublies pas.",
        "Done: a reminder at 8, not daily, like you asked.",
        "I'll remind you every day at 8 if you like.",
        "Like you asked, I can make it daily.",
        "A daily reminder at 8 so you don't forget?",
        "I'll remind you at 8 to take your daily vitamins.",
        "Ich erinnere dich um 8 Uhr an deine täglichen Tabletten.",
        "Je te rappellerai à 8h de faire ton footing quotidien.",
        "Te recordaré a las 8 tu paseo diario.",
        "Îți voi aminti la 8 de plimbarea zilnică.",
        "Done, it goes off daily at 8.",
        "I'll remind you at 8 to take the pill you take every morning.",
        "I'll remind you at 8 about the walk that you take each evening.",
        "Ich erinnere dich um 8 an die Tablette, die du jeden Morgen nimmst.",
        "Je te rappellerai à 8h de prendre le cachet que tu prends chaque matin.",
        "Te recordaré a las 8 tomar la pastilla que tomas cada mañana.",
        "Îți voi aminti la 8 să iei pastila pe care o iei în fiecare dimineață.",
    ],
)
def test_a_reply_for_one_time_or_saying_no_repeat_names_none(reply: str) -> None:
    assert not names_repeat(reply)


def _result(content: str, *, error: bool = False) -> ToolResult:
    return ToolResult(call_id="c", content=content, is_error=error)


def _run(name: str, **arguments: object) -> ToolCall:
    return ToolCall(id="c", name=name, arguments=arguments)


@pytest.mark.parametrize(
    ("call", "result", "held", "after"),
    [
        (_run(SCHEDULE_TOOL_NAME, at_time="17:30"), _result(_DAILY), (), ("abc",)),
        (_run(SCHEDULE_TOOL_NAME, at_time="17:30"), _result(_HELD), (), ("abc",)),
        (_run(SCHEDULE_TOOL_NAME, at_time="17:30"), _result(_DAILY), ("abc",), ("abc",)),
        (_run(SCHEDULE_TOOL_NAME, at_time="17:30"), _result(_DAILY), ("x",), ("x", "abc")),
        (_run(SCHEDULE_TOOL_NAME, at="2026-11-07T17:30"), _result(_ONCE), (), ()),
        (_run(SCHEDULE_TOOL_NAME, at_time="17:30", on_days=["mon"]), _result(_WEEKLY), (), ()),
        (_run(SCHEDULE_TOOL_NAME, at_time="17:30"), _result(_DAILY, error=True), (), ()),
        (_run(SCHEDULE_TOOL_NAME, at_time="17:30"), _result(DAILY_NOTE), (), ()),
        (_run(EDIT_SCHEDULED_TOOL_NAME, id="abc", every_seconds=0), _result(_ONCE), ("abc",), ()),
        (_run(EDIT_SCHEDULED_TOOL_NAME, id="abc", on_days=["mon"]), _result(""), ("abc",), ()),
        (_run(EDIT_SCHEDULED_TOOL_NAME, id="abc", text="gas"), _result(""), ("abc",), ("abc",)),
        (_run(EDIT_SCHEDULED_TOOL_NAME, id="x", every_seconds=0), _result(""), ("abc",), ("abc",)),
        (
            _run(EDIT_SCHEDULED_TOOL_NAME, id="abc", every_seconds=0),
            _result("", error=True),
            ("abc",),
            ("abc",),
        ),
        (_run(CANCEL_SCHEDULED_TOOL_NAME, id="abc"), _result(""), ("abc", "x"), ("x",)),
        (_run("list_scheduled", id="abc"), _result(_DAILY), ("abc",), ("abc",)),
    ],
)
def test_the_daily_ids_follow_each_store_edit_and_cancel(
    call: ToolCall, result: ToolResult, held: tuple[str, ...], after: tuple[str, ...]
) -> None:
    assert daily_after(call, result, held) == after


async def test_the_tool_s_own_daily_result_is_read_as_a_daily_store() -> None:
    tool = ScheduleTaskTool(
        InMemoryScheduleStore(), TickingClock(), tasks_enabled=False, max_active=8
    )
    call = _run(SCHEDULE_TOOL_NAME, kind="reminder", text="Wäsche", at_time="17:30")
    result = await tool.invoke(call)
    item = result.content.split()[2].rstrip(":")
    assert daily_after(call, result, ()) == (item,)


def _closed(reply: str, daily: tuple[str, ...]) -> str:
    parts = [reply]
    taint = TaintLedger(daily_stored=daily)
    runs = (ToolRun(name=SCHEDULE_TOOL_NAME, ok=True),)
    list(limit_notes(StopLedger(), runs, parts, caps=TurnCapabilities(), taint=taint, query=""))
    return "".join(parts)


@pytest.mark.parametrize(
    ("reply", "daily", "noted"),
    [
        ("Ich habe dich für 17:30 Uhr an die Wäsche erinnert.", ("abc",), True),
        ("Je te rappellerai à 17h30 d'appeler le plombier.", ("abc",), True),
        ("I'll remind you at 17:30, it does not repeat.", ("abc",), True),
        ("Ich erinnere dich jeden Tag um 17:30 Uhr an die Wäsche.", ("abc",), False),
        ("I'll remind you every day at 17:30.", ("abc",), False),
        ("Ich habe dich für 17:30 Uhr an die Wäsche erinnert.", (), False),
    ],
)
def test_a_reply_naming_no_repeat_over_a_daily_store_gets_the_note(
    reply: str, daily: tuple[str, ...], *, noted: bool
) -> None:
    assert _closed(reply, daily) == (reply + DAILY_STORED_NOTE if noted else reply)


async def _loop(calls: list[ToolCall]) -> TaintLedger:
    async def handler(arguments: Mapping[str, object]) -> str:
        return str(arguments["result"])

    tools = {
        name: (ToolSpec(name=name, description="s", parameters={}), handler)
        for name in (SCHEDULE_TOOL_NAME, EDIT_SCHEDULED_TOOL_NAME)
    }
    taint = TaintLedger()
    context = ToolLoopContext(
        dispatcher=ToolDispatcher(
            InMemoryToolRegistry(tools), RecordingAuditSink(), TickingClock()
        ),
        clock=TickingClock(),
        turn_id="t",
        taint=taint,
        nonce="n",
        session_id="s",
        query=_WASH,
    )
    working = [Message(role=Role.USER, text=_WASH, at=_AT, turn_id="t")]
    backend = ScriptedBrainBackend(chunks=("done",), tool_calls=calls)
    _ = [event async for event in stream_tool_loop(backend, "m", working, context)]
    return taint


_SET = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments={"at_time": "17:30", "result": _DAILY})
_ONE_TIME = ToolCall(
    id="c2",
    name=EDIT_SCHEDULED_TOOL_NAME,
    arguments={"id": "abc", "every_seconds": 0, "result": "edited abc"},
)


@pytest.mark.parametrize(
    ("calls", "daily"), [([_SET], ("abc",)), ([_SET, _ONE_TIME], ()), ([], ())]
)
async def test_a_turn_records_the_daily_items_it_left(
    calls: list[ToolCall], daily: tuple[str, ...]
) -> None:
    assert (await _loop(calls)).daily_stored == daily
