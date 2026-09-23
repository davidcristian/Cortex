import asyncio
import os
from datetime import UTC, datetime
from typing import cast

import pytest
from grpc import aio

from cortex_core import ScheduledItem, ScheduleKind
from cortex_seam import (
    RPC_TOKEN_HEADER,
    AckReminderReply,
    AckReminderRequest,
    BrainServiceStub,
    DueReminder,
    ListDueRemindersReply,
    ListDueRemindersRequest,
)
from cortex_session import DEFAULT_REDIS_URL, RedisScheduleStore

_RPC_ENDPOINT = os.environ.get("CORTEX_SEAM_ENDPOINT", "127.0.0.1:50051")
_ATTEMPTS = 40
_RETRY_S = 0.5


def _metadata() -> tuple[tuple[str, str], ...] | None:
    token = os.environ.get("CORTEX_SEAM_TOKEN", "")
    return ((RPC_TOKEN_HEADER, token),) if token else None


async def _list(stub: BrainServiceStub) -> ListDueRemindersReply:
    method = stub.ListDueReminders  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast(
        "ListDueRemindersReply", await method(ListDueRemindersRequest(), metadata=_metadata())
    )


async def _ack(stub: BrainServiceStub, fired: DueReminder) -> AckReminderReply:
    method = stub.AckReminder  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    request = AckReminderRequest(
        reminder_id=fired.reminder_id, fired_at_unix_ms=fired.fired_at_unix_ms
    )
    return cast("AckReminderReply", await method(request, metadata=_metadata()))


async def _wait_for_fire(stub: BrainServiceStub, item_id: str) -> DueReminder | None:
    for _ in range(_ATTEMPTS):
        reply = await _list(stub)
        fired = [r for r in reply.reminders if r.reminder_id == item_id]
        if fired:
            return fired[0]
        await asyncio.sleep(_RETRY_S)
    return None


@pytest.mark.integration
async def test_reminder_fires_and_round_trips_over_the_live_rpc() -> None:
    url = os.environ.get("CORTEX_REDIS_URL", DEFAULT_REDIS_URL)
    store = RedisScheduleStore.from_url(url)
    now = datetime.now(UTC)
    item_id = f"live-seam-{int(now.timestamp())}"
    await store.add(
        ScheduledItem(
            id=item_id,
            kind=ScheduleKind.REMINDER,
            text="live fire proof",
            session_id="live-seam",
            due_at=now,
            created_at=now,
        )
    )
    try:
        async with aio.insecure_channel(_RPC_ENDPOINT) as channel:
            stub = BrainServiceStub(channel)
            fired = await _wait_for_fire(stub, item_id)
            assert fired is not None, "the ticker did not fire the seeded reminder in time"
            assert fired.text == "live fire proof"
            assert fired.recurring is False
            assert fired.tainted is False
            assert fired.session_id == "live-seam"
            assert (await _ack(stub, fired)).acked is True
            assert [r for r in (await _list(stub)).reminders if r.reminder_id == item_id] == []
            assert (await _ack(stub, fired)).acked is False
    finally:
        await store.cancel(item_id)
        await store.aclose()
