from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from swap_harness import ScriptedBrainBackend, TickingClock

from cortex_core import (
    CancelScheduledTool,
    InMemoryScheduleStore,
    InMemoryToolRegistry,
    Message,
    RecordingAuditSink,
    RecordingConfirmer,
    Role,
    ScheduledItem,
    ScheduleKind,
    ScheduleStoreError,
    StopLedger,
    TaintLedger,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolRun,
    TurnCapabilities,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.schedule_cancelled import (
    CANCELLED_CHARS,
    CANCELLED_NOTE,
    CANCELLED_NOTES,
    cancelled_after,
    cancelled_notes,
)
from cortex_core.schedule_claim import UNSCHEDULED_CLAIM_NOTE
from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME
from cortex_core.schedule_verbs import (
    CANCEL_SCHEDULED_TOOL_NAME,
    EDIT_SCHEDULED_TOOL_NAME,
    SNOOZE_SCHEDULED_TOOL_NAME,
)
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 11, 11, 5, 0, tzinfo=UTC)
_CHANGE = "Change my plant reminder to 9:30 every day from tomorrow on."
_PLANTS = "water the plants"
_LISTED = ToolRun(name="list_scheduled", ok=True)
_CANCEL = ToolRun(name=CANCEL_SCHEDULED_TOOL_NAME, ok=True)


def _item(item_id: str = "abc", text: str = _PLANTS) -> ScheduledItem:
    return ScheduledItem(
        id=item_id,
        kind=ScheduleKind.REMINDER,
        text=text,
        session_id="s",
        due_at=_AT + timedelta(hours=5),
        created_at=_AT,
        every=timedelta(days=1),
    )


class _UnreadableStore(InMemoryScheduleStore):
    async def get(self, item_id: str) -> ScheduledItem | None:
        msg = f"corrupt record {item_id}"
        raise ScheduleStoreError(msg)


def _cancel_call(item_id: str = "abc") -> ToolCall:
    return ToolCall(id="c1", name=CANCEL_SCHEDULED_TOOL_NAME, arguments={"id": item_id})


async def test_a_cancel_result_holds_the_stored_text_of_the_item_it_deleted() -> None:
    store = InMemoryScheduleStore()
    await store.add(_item())
    result = await CancelScheduledTool(store).invoke(_cancel_call())
    assert (result.content, result.cancelled) == ("cancelled abc", _PLANTS)
    assert await store.get("abc") is None


async def test_a_record_that_cannot_be_read_is_still_cancelled_and_named_by_its_id() -> None:
    store = _UnreadableStore()
    await store.add(_item())
    result = await CancelScheduledTool(store).invoke(_cancel_call())
    assert not result.is_error
    assert result.cancelled == "abc"
    assert await store.list_active() == ()


async def test_an_item_stored_from_untrusted_content_is_named_by_its_id() -> None:
    store = InMemoryScheduleStore()
    await store.add(replace(_item(), tainted=True))
    result = await CancelScheduledTool(store).invoke(_cancel_call())
    assert result.cancelled == "abc"


async def test_a_cancel_of_an_unknown_id_names_no_deleted_item() -> None:
    result = await CancelScheduledTool(InMemoryScheduleStore()).invoke(_cancel_call("ghost"))
    assert result.is_error
    assert not result.cancelled


def test_the_ledger_adds_each_deleted_item_and_keeps_its_list_for_any_other_result() -> None:
    deleted = ToolResult(call_id="c", content="cancelled abc", cancelled=_PLANTS)
    assert cancelled_after(deleted, ("pills",)) == ("pills", _PLANTS)
    assert cancelled_after(ToolResult(call_id="c", content="edited"), ("pills",)) == ("pills",)


def _closed(
    runs: tuple[ToolRun, ...], cancelled: tuple[str, ...], reply: str, query: str = _CHANGE
) -> str:
    parts = [reply]
    taint = TaintLedger(cancelled=cancelled)
    caps = TurnCapabilities()
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=query))
    return "".join(parts)


@pytest.mark.parametrize(
    ("reply", "query"),
    [
        ("Done, your plant reminder is now at 9:30 every day.", _CHANGE),
        ("I've cancelled your plant reminder.", "Cancel my plant reminder."),
    ],
)
def test_a_turn_whose_only_change_was_a_cancel_names_the_deleted_item(
    *, reply: str, query: str
) -> None:
    closed = _closed((_LISTED, _CANCEL), (_PLANTS,), reply, query)
    assert closed.startswith(reply)
    assert closed.endswith(f"{CANCELLED_NOTE}\n- {_PLANTS})")


def test_a_reply_claiming_an_update_also_keeps_the_unscheduled_claim_note() -> None:
    closed = _closed((_LISTED, _CANCEL), (_PLANTS,), "I've updated your plant reminder.")
    assert UNSCHEDULED_CLAIM_NOTE in closed
    assert closed.index(UNSCHEDULED_CLAIM_NOTE) < closed.index(CANCELLED_NOTE.strip())


@pytest.mark.parametrize(
    "later",
    [
        ToolRun(name=SCHEDULE_TOOL_NAME, ok=True),
        ToolRun(name=EDIT_SCHEDULED_TOOL_NAME, ok=True),
        ToolRun(name=SNOOZE_SCHEDULED_TOOL_NAME, ok=True),
    ],
)
def test_a_cancel_beside_a_successful_store_edit_or_snooze_has_no_note(later: ToolRun) -> None:
    reply = "I replaced your plant reminder with one at 9:30."
    assert _closed((_CANCEL, later), (_PLANTS,), reply) == reply


def test_a_change_made_by_an_edit_with_no_cancel_has_no_note() -> None:
    reply = "I moved your plant reminder to 9:30."
    assert _closed((ToolRun(name=EDIT_SCHEDULED_TOOL_NAME, ok=True),), (), reply) == reply


def test_a_failed_store_after_the_cancel_still_names_the_deleted_item() -> None:
    failed = ToolRun(name=SCHEDULE_TOOL_NAME, ok=False)
    notes = cancelled_notes((_CANCEL, failed), (_PLANTS,))
    assert notes == (f"{CANCELLED_NOTE}\n- {_PLANTS})",)


def test_every_deleted_item_is_named_on_one_line_cut_to_its_limit() -> None:
    long = "call the landlord about\nthe heating " + "x" * 100
    (note,) = cancelled_notes((_CANCEL, _CANCEL), (_PLANTS, long))
    first, second = note.removeprefix(CANCELLED_NOTE).removesuffix(")").splitlines()[1:]
    assert first == f"- {_PLANTS}"
    assert second.startswith("- call the landlord about the heating x")
    assert len(second) == len("- ") + CANCELLED_CHARS
    assert second.endswith("...")


@pytest.mark.parametrize(
    ("query", "language"),
    [
        ("Ändere meine Pflanzen-Erinnerung auf 9:30 Uhr, bitte.", "de"),
        ("Change mon rappel des plantes à 9h30 demain, et merci.", "fr"),
    ],
)
def test_the_note_is_written_in_the_language_of_the_message(*, query: str, language: str) -> None:
    closed = _closed((_CANCEL,), ("Pflanzen gießen",), "Erledigt.", query)
    assert closed == f"Erledigt.{CANCELLED_NOTES[language]}\n- Pflanzen gießen)"


def test_the_english_note_is_the_plain_sentence() -> None:
    assert CANCELLED_NOTE == "\n\n(Deleted in this turn, with nothing scheduled in its place:"


@pytest.mark.parametrize(
    ("language", "opening"),
    [
        ("fr", "(Ce qui suit a été supprimé ici,"),
        ("de", "(Folgendes wurde hier gelöscht,"),
        ("es", "(Se eliminó aquí lo siguiente,"),
        ("ro", "(Ce urmează a fost șters aici,"),
    ],
)
def test_each_translated_note_states_the_deletion_and_ends_before_the_list(
    *, language: str, opening: str
) -> None:
    note = CANCELLED_NOTES[language]
    assert note.removeprefix("\n\n").startswith(opening)
    assert note.endswith(":")


async def _turn(*, approve: bool) -> TaintLedger:
    store = InMemoryScheduleStore()
    await store.add(_item())
    tool = CancelScheduledTool(store)

    async def handler(arguments: Mapping[str, object]) -> ToolResult:
        return await tool.invoke(
            ToolCall(id="c1", name=CANCEL_SCHEDULED_TOOL_NAME, arguments=arguments)
        )

    taint = TaintLedger()
    context = ToolLoopContext(
        dispatcher=ToolDispatcher(
            InMemoryToolRegistry({CANCEL_SCHEDULED_TOOL_NAME: (tool.spec, handler)}),
            RecordingAuditSink(),
            TickingClock(),
            confirmer=RecordingConfirmer(answer=approve),
        ),
        clock=TickingClock(),
        turn_id="t",
        taint=taint,
        nonce="n",
        session_id="s",
        query=_CHANGE,
    )
    working = [Message(role=Role.USER, text=_CHANGE, at=_AT, turn_id="t")]
    backend = ScriptedBrainBackend(chunks=("done",), tool_calls=(_cancel_call(),))
    _ = [event async for event in stream_tool_loop(backend, "m", working, context)]
    return taint


async def test_an_approved_cancel_in_a_turn_records_the_text_of_the_item_it_deleted() -> None:
    assert (await _turn(approve=True)).cancelled == (_PLANTS,)


async def test_a_denied_cancel_records_no_deleted_item() -> None:
    assert (await _turn(approve=False)).cancelled == ()
