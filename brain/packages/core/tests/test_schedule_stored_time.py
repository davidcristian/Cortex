from collections.abc import Mapping
from datetime import UTC, datetime

import pytest
from swap_harness import ScriptedBrainBackend, TickingClock

from cortex_core import (
    SCHEDULE_TOOL_NAME,
    InMemoryToolRegistry,
    Message,
    RecordingAuditSink,
    Role,
    TaintLedger,
    ToolCall,
    ToolDispatcher,
    ToolRun,
    ToolSpec,
    TurnCapabilities,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.schedule_claim import (
    MONTHLY_STORED_NOTE,
    STORED_TIME_NOTE,
    STORED_TIME_NOTES,
    names_time_of_day,
    stored_time,
)
from cortex_core.schedule_verbs import EDIT_SCHEDULED_TOOL_NAME, SNOOZE_SCHEDULED_TOOL_NAME
from cortex_core.stops import StopLedger
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 11, 6, 3, 0, 0, tzinfo=UTC)
_PARCEL = "Remind me on 14 December to post the parcel."
_MORNING = "scheduled reminder abc: due 2026-12-14T09:00:00+00:00 (in 38 days)"
_WEEKLY = "scheduled reminder abc: due 2026-11-09T09:00:00+00:00 (Monday), repeats weekly"
_SOON = "scheduled reminder abc: due 2026-11-06T03:10:00+00:00 (today)"
_MOVED = "edited abc: now due 2026-11-20T10:00:00+00:00"


@pytest.mark.parametrize(
    "reply",
    [
        "I've set a reminder for 14 December at 9:00 AM.",
        "I've set a reminder for 14 December at 09:00.",
        "I'll remind you at 9 am on 14 December.",
        "I'll remind you at 9 a.m.",
        "I'll remind you at 9AM.",
        "I'll remind you at noon on the 14th.",
        "I'll remind you at midnight.",
        "Je vous rappellerai d'appeler votre sœur demain à 17h30.",
        "Je vous le rappellerai à 9 h 15.",
        "Ich erinnere dich morgen um 9 Uhr.",
        "Ich erinnere dich um 9.30 Uhr an den Termin.",
        'J\'ai bien programmé un rappel pour demain à 18h : "Appeler Claire".',
        "Je vous le rappellerai vers 9h.",
        "Ich erinnere dich um 18h.",
        "Te lo recordaré mañana a las 18h.",
        "C'est fait ! Je vous rappellerai d'appeler le plombier aujourd'hui à 17h30.",
        "Je vous rappellerai le 15 de chaque mois à 10h00.",
        "Ich erinnere dich um 17h30.",
        "Te lo recordaré a las 17h30.",
        "I'll remind you at 17h30.",
        "Je vous le rappellerai vers 9h30.",
        "Rappel réglé pour 17h30.",
        "Je te le rappelle demain 17h30.",
        "C'est noté : rappel aujourd'hui, 17h30.",
        "Rappel programmé dès 17h30 demain.",
        "Le rappel est réglé pour 13h.",
        "Rappel noté pour 23h45.",
        "Le rappel est réglé pour 2h du matin.",
        "Rappel programmé pour 8h30 du soir.",
        "Rappel prévu pour 3 h de l\u2019après-midi.",
        "Je vous rappellerai demain à 9h de vider le casier.",
        "Je vous le rappelle à 9h de prendre vos médicaments.",
        "Rappel prévu pour **9h00** demain.",
        "Je vous le rappellerai à **9h**.",
        "Te lo recordaré a las 22.",
        "Te lo recordaré mañana a las 10 de la mañana.",
        "Te lo recordaré a la 1 de la tarde.",
        "Îți voi aminti mâine la ora 14.",
        "Îți voi aminti la ora 9 dimineața.",
        "Ich erinnere dich morgen um 14.",
        "Erinnerung gesetzt: um 15.",
        "Dein Wecker klingelt um 15.",
    ],
)
def test_a_clock_figure_am_or_pm_noon_or_midnight_names_a_time_of_day(reply: str) -> None:
    assert names_time_of_day(reply)


@pytest.mark.parametrize(
    "reply",
    [
        "I've set a reminder for 14 December to post the parcel.",
        "I'll remind you at nine in the morning on 14 December.",
        "I'll remind you on 14 December at 9.",
        "Set: a reminder every 4 weeks from 3 March.",
        "I'll remind you in 9 minutes.",
        "Mia's birthday on 9 August is set, every year.",
        "I made 5 amendments to the plan.",
        "I'll remind you in 2h.",
        "I'll remind you in 2h30.",
        "Je vous le rappellerai dans 2h30.",
        "Die Uhr im Flur geht 5 Minuten vor.",
        "Ich habe 3 Uhren gefunden.",
        "Je vous le rappellerai dans 2h.",
        "Le film dure 2h.",
        "J'ai dormi 2h.",
        "Je vous le rappellerai en 2 h.",
        "C'est à 2h de route.",
        "Ich habe 2h gewartet.",
        "Te lo recuerdo en 2h.",
        "La réunion dure 2h30.",
        "Le trajet prend 1h30, je te le rappelle demain.",
        "Je te le rappelle, le cours dure en 2h30.",
        "Rappel enregistré en 2h30.",
        "Je te le rappelle demain, pendant 1h30.",
        "Je te le rappelle toutes les 2h30.",
        "Te lo recuerdo mañana, para 1h30 de clase.",
        "Rappel enregistré pour demain dans 12 h 30.",
        "Je pars pour 2h30.",
        "Il a 2h30 de retard.",
        "C'est à 2h30 de route.",
        "Ich habe 2h30 gewartet.",
        "Le vol dure 13h30.",
        "Rappel enregistré, version 2h1.",
        "Je te le rappellerai dans 24h.",
        "Je te le rappellerai d'ici 2h.",
        "I'll remind you within 24h.",
        "Te lo recuerdo en 24h.",
        "Il part demain pour 2h30.",
        "Rappel réglé pour demain, pendant 1h30.",
        "Il reste aujourd'hui 2h30 de travail.",
        "Demain, 2h30 de trajet.",
        "Le trajet prend 1h30 dès demain.",
        "Le minuteur est réglé pour 2h.",
        "C'est réglé pour 2h : je te préviens quand elles sont passées.",
        "Le rappel est programmé pour 2h à partir de maintenant.",
        "Le minuteur est réglé pour 2 h 30.",
        "C'est noté pour 1h.",
        "Le minuteur est réglé pour 12h.",
        "Le four est réglé pour 2h de cuisson.",
        "Rappel réglé pour 18h de route.",
        "C'est à 9h de route.",
        "C'est à 2h de voiture.",
        "La ville est à 3 h de marche.",
        "C'est à 9h de chantier.",
        "Rappel : la ville est à 2h de voiture.",
        "Le minuteur est réglé pour 2h30.",
        "Te lo recordaré a las 10.",
        "Te lo recordaré mañana a las 10.",
        "Envía el correo a las 14 personas.",
        "Hice las 10 tareas.",
        "Te lo recordaré a las 14,5.",
        "Te lo recuerdo en 10 minutos.",
        "Îți voi aminti la ora 9.",
        "Îți voi aminti la ora 14 din program.",
        "Am citit ora 14 din program.",
        "Ich erinnere dich um 9.",
        "Der Preis steigt um 14 Prozent.",
        "Verschieb es um 14 Tage.",
        "Am 14.11 erinnere ich dich.",
        "Ich habe 14 Dateien gefunden.",
        "Der Preis stieg um 15.",
        "Die Dosis sinkt um 20.",
        "Ich erinnere dich morgen. Der Preis stieg um 15.",
        "Hay que pasar a la 15.",
        "Vuelve a la 14.",
    ],
)
def test_a_reply_with_no_clock_figure_names_no_time_of_day(reply: str) -> None:
    assert not names_time_of_day(reply)


@pytest.mark.parametrize(
    ("name", "arguments", "result", "time"),
    [
        (SCHEDULE_TOOL_NAME, {"at": "2026-12-14T09:00:00"}, _MORNING, "09:00"),
        (SCHEDULE_TOOL_NAME, {"at_time": "09:00", "on_days": ["mon"]}, _WEEKLY, "09:00"),
        (SCHEDULE_TOOL_NAME, {"at": "2026-12-14T00:00:00"}, _MORNING.replace("09", "00"), "00:00"),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "on_month_days": [20]}, _MOVED, "10:00"),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "text": "gas"}, "edited abc", ""),
        (SCHEDULE_TOOL_NAME, {"in_seconds": 600}, _SOON, ""),
        (SCHEDULE_TOOL_NAME, {"every_seconds": 7200}, _SOON, ""),
        (SCHEDULE_TOOL_NAME, {"at": None, "at_time": None}, _MORNING, ""),
        (SCHEDULE_TOOL_NAME, {"at": "2026-12-14T09:00:00"}, "REFUSED: not run", ""),
        (SNOOZE_SCHEDULED_TOOL_NAME, {"id": "abc"}, "snoozed abc: now due 2026-11-06T10:00:00", ""),
        ("set_volume", {"at": "2026-12-14T09:00:00"}, _MORNING, ""),
    ],
)
def test_the_stored_time_is_read_from_a_timed_schedule_or_edit_result(
    name: str, arguments: Mapping[str, object], result: str, time: str
) -> None:
    assert stored_time(ToolCall(id="c", name=name, arguments=arguments), result) == time


def _closed(reply: str, time: str, query: str = "") -> str:
    parts = [reply]
    taint = TaintLedger(stored_time=time)
    runs = (ToolRun(name=SCHEDULE_TOOL_NAME, ok=True),)
    list(limit_notes(StopLedger(), runs, parts, caps=TurnCapabilities(), taint=taint, query=query))
    return "".join(parts)


@pytest.mark.parametrize(
    ("reply", "time", "noted"),
    [
        ("I've set a reminder for 14 December to post the parcel.", "09:00", True),
        ("I'll remind you at nine in the morning on 14 December.", "09:00", True),
        ("I'll remind you on 14 December at 9.", "09:00", True),
        ("Moved: the gas bill reminder is now on the 20th of every month.", "10:00", True),
        ("I've set a reminder for 14 December at 9:00 AM.", "09:00", False),
        ("I'll remind you at noon on the 14th.", "12:00", False),
        ("I'll remind you at midnight on 14 December.", "00:00", False),
        ("C'est fait ! Je vous rappellerai demain à 17h30.", "17:30", False),
        ("Alles klar, ich erinnere dich morgen um 9 Uhr.", "09:00", False),
        ("C'est réglé pour 2h : je te préviens quand elles sont passées.", "03:40", True),
        ("C'est réglé pour 17h30, je te préviens.", "17:30", False),
        ("I've set a reminder for 14 December to post the parcel.", "", False),
    ],
)
def test_a_reply_naming_no_time_over_a_stored_time_gets_the_note(
    reply: str, time: str, *, noted: bool
) -> None:
    shown = _closed(reply, time)
    expected = reply + STORED_TIME_NOTE.format(time=time) if noted else reply
    assert shown == expected


@pytest.mark.parametrize(
    ("query", "language"),
    [
        ("Rappelle-moi le 14 décembre d'envoyer le colis.", "fr"),
        ("Erinnere mich am 14. Dezember an das Paket.", "de"),
        ("Recuérdame el 14 de diciembre enviar el paquete.", "es"),
        ("Amintește-mi pe 14 decembrie să trimit coletul.", "ro"),
    ],
)
def test_a_stored_time_note_is_written_in_the_language_of_the_message(
    query: str, language: str
) -> None:
    reply = "OK, 14.12."
    expected = reply + STORED_TIME_NOTES[language].format(time="09:00", las="las")
    assert _closed(reply, "09:00", query) == expected


@pytest.mark.parametrize(
    ("query", "time", "phrase"),
    [
        ("Recuérdame el 14 de diciembre enviar el paquete.", "01:30", "es a la 01:30."),
        ("Recuérdame el 14 de diciembre enviar el paquete.", "01:00", "es a la 01:00."),
        ("Recuérdame el 14 de diciembre enviar el paquete.", "11:30", "es a las 11:30."),
        ("Recuérdame el 14 de diciembre enviar el paquete.", "21:00", "es a las 21:00."),
        ("Recuérdame el 14 de diciembre enviar el paquete.", "00:30", "es a las 00:30."),
        ("Recuérdame el 14 de diciembre enviar el paquete.", "10:01", "es a las 10:01."),
        ("Rappelle-moi le 14 décembre d'envoyer le colis.", "01:30", "fixé à 01:30."),
        ("Erinnere mich am 14. Dezember an das Paket.", "01:30", "ist auf 01:30 gestellt."),
        ("Amintește-mi pe 14 decembrie să trimit coletul.", "01:30", "la ora 01:30."),
    ],
)
def test_the_spanish_note_writes_a_la_only_for_one_oclock(
    query: str, time: str, phrase: str
) -> None:
    assert phrase in _closed("OK, 14.12.", time, query)


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
        query=_PARCEL,
    )
    working = [Message(role=Role.USER, text=_PARCEL, at=_AT, turn_id="t")]
    backend = ScriptedBrainBackend(chunks=("done",), tool_calls=calls)
    _ = [event async for event in stream_tool_loop(backend, "m", working, context)]
    return taint


_SET = ToolCall(
    id="c1", name=SCHEDULE_TOOL_NAME, arguments={"at": "2026-12-14T09:00:00", "result": _MORNING}
)
_EDIT = ToolCall(
    id="c2",
    name=EDIT_SCHEDULED_TOOL_NAME,
    arguments={"id": "abc", "on_month_days": [20], "result": _MOVED},
)
_RELATIVE = ToolCall(
    id="c3", name=SCHEDULE_TOOL_NAME, arguments={"in_seconds": 600, "result": _SOON}
)


@pytest.mark.parametrize(
    ("calls", "time"),
    [
        ([_SET], "09:00"),
        ([_SET, _EDIT], "10:00"),
        ([_SET, _RELATIVE], "09:00"),
        ([_RELATIVE], ""),
        ([], ""),
    ],
)
async def test_the_last_timed_call_that_ran_sets_the_stored_time(
    calls: list[ToolCall], time: str
) -> None:
    assert (await _loop(calls)).stored_time == time


@pytest.mark.parametrize(
    ("note", "opening"),
    [
        (MONTHLY_STORED_NOTE, "(A reminder set in this turn repeats"),
        (STORED_TIME_NOTE, "(A reminder set or changed in this turn is at"),
        (STORED_TIME_NOTES["fr"], "(Un rappel créé ou modifié ici"),
        (STORED_TIME_NOTES["de"], "(Eine hier erstellte oder geänderte Erinnerung"),
        (STORED_TIME_NOTES["es"], "(Un recordatorio creado o cambiado aquí"),
        (STORED_TIME_NOTES["ro"], "(Un memento creat sau modificat aici"),
    ],
)
def test_a_note_names_one_reminder_of_the_turn_and_not_its_only_one(
    note: str, opening: str
) -> None:
    assert note.removeprefix("\n\n").startswith(opening)
