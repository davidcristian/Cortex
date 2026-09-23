from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import cast

import grpc
import pytest
from grpc import aio

from cortex_core import (
    CalendarRule,
    EchoInferenceBackend,
    FireOutcome,
    InMemoryScheduleStore,
    InMemorySessionStore,
    ScheduledItem,
    ScheduleKind,
    ScheduleStore,
    ScheduleStoreError,
    SystemClock,
    TurnEngine,
)
from cortex_orchestrator import RpcPorts, RpcServerConfig, create_server
from cortex_orchestrator.reminders import reminder_to_proto
from cortex_seam import (
    AckReminderReply,
    AckReminderRequest,
    BrainServiceStub,
    ListDueRemindersReply,
    ListDueRemindersRequest,
)

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)


async def _list(stub: BrainServiceStub) -> ListDueRemindersReply:
    method = stub.ListDueReminders  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast("ListDueRemindersReply", await method(ListDueRemindersRequest()))


async def _ack(stub: BrainServiceStub, reminder_id: str, fired_at_unix_ms: int) -> AckReminderReply:
    method = stub.AckReminder  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    request = AckReminderRequest(reminder_id=reminder_id, fired_at_unix_ms=fired_at_unix_ms)
    return cast("AckReminderReply", await method(request))


async def _serve(schedules: ScheduleStore | None) -> tuple[aio.Server, str]:
    """A BrainService over `schedules` on an ephemeral loopback port."""
    store = InMemorySessionStore()
    engine = TurnEngine(store, EchoInferenceBackend(), SystemClock())
    server, port = create_server(
        RpcServerConfig(host="127.0.0.1", port=0),
        lambda _confirmer, _progress: engine,
        store,
        RpcPorts(schedules=schedules),
    )
    await server.start()
    return server, f"127.0.0.1:{port}"


async def _fired_reminder(
    store: InMemoryScheduleStore,
    item_id: str,
    *,
    tainted: bool = False,
    recurring: bool = False,
    at: datetime = _NOW,
) -> None:
    """Seed one reminder and fire it to deliverable, the way the ticker would."""
    every = timedelta(hours=1) if recurring else None
    await store.add(
        ScheduledItem(
            id=item_id,
            kind=ScheduleKind.REMINDER,
            text=f"text of {item_id}",
            session_id="chat-1",
            due_at=at,
            created_at=at,
            every=every,
            tainted=tainted,
        )
    )
    (claim,) = await store.claim_due(at, lease=timedelta(minutes=5), limit=8)
    next_at = at + timedelta(hours=1) if recurring else None
    outcome = FireOutcome(fired_at=at, next_due=next_at, deliverable=True)
    assert await store.finish(claim, outcome) is True


async def _fired_task(store: InMemoryScheduleStore, item_id: str, *, outcome: str) -> None:
    """Seed one task and fire it to deliverable with an outcome, the way the ticker would."""
    await store.add(
        ScheduledItem(
            id=item_id,
            kind=ScheduleKind.TASK,
            text=f"instruction of {item_id}",
            session_id="chat-1",
            due_at=_NOW,
            created_at=_NOW,
        )
    )
    (claim,) = await store.claim_due(_NOW, lease=timedelta(minutes=5), limit=8)
    fired = FireOutcome(fired_at=_NOW, next_due=None, deliverable=True, outcome=outcome)
    assert await store.finish(claim, fired) is True


async def test_list_due_reminders_maps_the_deliverable_view() -> None:
    schedules = InMemoryScheduleStore()
    await _fired_reminder(schedules, "r1", tainted=True, recurring=True)
    server, address = await _serve(schedules)
    try:
        async with aio.insecure_channel(address) as channel:
            reply = await _list(BrainServiceStub(channel))
    finally:
        await server.stop(grace=None)
    (reminder,) = reply.reminders
    assert reminder.reminder_id == "r1"
    assert reminder.text == "text of r1"
    assert reminder.fired_at_unix_ms == int(_NOW.timestamp() * 1000)
    assert reminder.recurring is True
    assert reminder.tainted is True
    assert reminder.session_id == "chat-1"


async def test_list_due_reminders_maps_a_task_outcome() -> None:
    schedules = InMemoryScheduleStore()
    await _fired_task(schedules, "t1", outcome="[subagent 1] 3 emails need replies")
    server, address = await _serve(schedules)
    try:
        async with aio.insecure_channel(address) as channel:
            reply = await _list(BrainServiceStub(channel))
    finally:
        await server.stop(grace=None)
    (notice,) = reply.reminders
    assert notice.reminder_id == "t1"
    assert notice.text == "[subagent 1] 3 emails need replies"
    assert notice.session_id == "chat-1"


def test_reminder_to_proto_falls_back_to_text_without_a_task_outcome() -> None:
    item = ScheduledItem(
        id="t1",
        kind=ScheduleKind.TASK,
        text="instruction of t1",
        session_id="chat-1",
        due_at=_NOW,
        created_at=_NOW,
        deliverable_since=_NOW,
        last_outcome=None,
    )
    assert reminder_to_proto(item).text == "instruction of t1"


@pytest.mark.parametrize(
    ("every", "rule", "expected"),
    [
        (None, None, False),
        (timedelta(hours=1), None, True),
        (None, CalendarRule(hour=9, minute=0), True),
    ],
)
def test_reminder_to_proto_recurs_by_either_mechanism(
    *, every: timedelta | None, rule: CalendarRule | None, expected: bool
) -> None:
    item = ScheduledItem(
        id="r1",
        kind=ScheduleKind.REMINDER,
        text="text of r1",
        session_id="chat-1",
        due_at=_NOW,
        created_at=_NOW,
        every=every,
        rule=rule,
        deliverable_since=_NOW,
    )
    assert reminder_to_proto(item).recurring is expected


async def test_ack_reminder_clears_the_slot_and_is_idempotent() -> None:
    schedules = InMemoryScheduleStore()
    await _fired_reminder(schedules, "r1")
    server, address = await _serve(schedules)
    try:
        async with aio.insecure_channel(address) as channel:
            stub = BrainServiceStub(channel)
            (listed,) = (await _list(stub)).reminders
            assert (await _ack(stub, "r1", listed.fired_at_unix_ms)).acked is True
            assert (await _list(stub)).reminders == []
            assert (await _ack(stub, "r1", listed.fired_at_unix_ms)).acked is False
    finally:
        await server.stop(grace=None)


async def test_schedule_free_brain_answers_benignly() -> None:
    server, address = await _serve(None)
    try:
        async with aio.insecure_channel(address) as channel:
            stub = BrainServiceStub(channel)
            assert (await _list(stub)).reminders == []
            assert (await _ack(stub, "ghost", 1)).acked is False
    finally:
        await server.stop(grace=None)


class _FailingScheduleStore(InMemoryScheduleStore):
    """A store whose reads and acks always raise, for the abort paths."""

    def _down(self) -> ScheduleStoreError:
        msg = "redis down"
        return ScheduleStoreError(msg)

    async def deliverable(self) -> Sequence[ScheduledItem]:
        raise self._down()

    async def ack(self, item_id: str, *, fired_at: datetime | None) -> bool:
        del item_id, fired_at
        raise self._down()


@pytest.mark.parametrize("rpc", ["list", "ack"])
async def test_store_failure_aborts_unavailable(rpc: str) -> None:
    server, address = await _serve(_FailingScheduleStore())
    try:
        async with aio.insecure_channel(address) as channel:
            stub = BrainServiceStub(channel)
            with pytest.raises(aio.AioRpcError) as excinfo:
                await (_list(stub) if rpc == "list" else _ack(stub, "r1", 1))
    finally:
        await server.stop(grace=None)
    assert excinfo.value.code() == grpc.StatusCode.UNAVAILABLE
    assert "redis down" in str(excinfo.value.details())


async def test_an_ack_naming_a_replaced_fire_leaves_the_later_one_due() -> None:
    schedules = InMemoryScheduleStore()
    await _fired_reminder(schedules, "r1", recurring=True)
    server, address = await _serve(schedules)
    try:
        async with aio.insecure_channel(address) as channel:
            stub = BrainServiceStub(channel)
            (listed,) = (await _list(stub)).reminders
            stale = listed.fired_at_unix_ms - 1
            assert (await _ack(stub, "r1", stale)).acked is False
            (still,) = (await _list(stub)).reminders
            assert still.fired_at_unix_ms == listed.fired_at_unix_ms
    finally:
        await server.stop(grace=None)


async def test_an_unstamped_ack_from_an_older_body_clears_the_held_fire() -> None:
    schedules = InMemoryScheduleStore()
    await _fired_reminder(schedules, "r1")
    server, address = await _serve(schedules)
    try:
        async with aio.insecure_channel(address) as channel:
            stub = BrainServiceStub(channel)
            assert (await _ack(stub, "r1", 0)).acked is True
            assert (await _list(stub)).reminders == []
    finally:
        await server.stop(grace=None)


async def test_a_stamp_no_datetime_can_hold_names_no_fire() -> None:
    schedules = InMemoryScheduleStore()
    await _fired_reminder(schedules, "r1")
    server, address = await _serve(schedules)
    try:
        async with aio.insecure_channel(address) as channel:
            stub = BrainServiceStub(channel)
            assert (await _ack(stub, "r1", 2**62)).acked is False
            assert len((await _list(stub)).reminders) == 1
    finally:
        await server.stop(grace=None)


async def test_the_listed_stamp_is_the_one_the_ack_compares() -> None:
    at = datetime(2038, 3, 19, 11, 38, 59, 812000, tzinfo=UTC)
    assert int(at.timestamp() * 1000) == 2152611539811
    schedules = InMemoryScheduleStore()
    await _fired_reminder(schedules, "r1", at=at)
    server, address = await _serve(schedules)
    try:
        async with aio.insecure_channel(address) as channel:
            stub = BrainServiceStub(channel)
            (listed,) = (await _list(stub)).reminders
            assert listed.fired_at_unix_ms == 2152611539812
            assert (await _ack(stub, "r1", listed.fired_at_unix_ms)).acked is True
    finally:
        await server.stop(grace=None)
