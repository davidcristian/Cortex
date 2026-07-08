"""The end-to-end reminder fire over the live seam (ADR-0025): seed → ticker → pull → ack.

Integration-marked: excluded from CI and the coverage gate by the workspace addopts; run
manually against the compose stack with scheduling on:

    CORTEX_SCHEDULE_BACKEND=redis docker compose --project-directory . \
      -f docker/docker-compose.yml up -d --build
    cd brain && uv run pytest -m integration --no-cov \
      packages/orchestrator/tests/test_schedule_live_seam.py

It seeds a due reminder directly into the store (`CORTEX_REDIS_URL`, loopback-published),
waits for the brain's ticker to fire it, reads it back over `ListDueReminders`, acks it over
`AckReminder`, and cleans up after itself. That proves the durable store, the ticker, the
orchestrator handlers, and the gRPC seam end to end against the real containers.
"""

import asyncio
import os
from datetime import UTC, datetime
from typing import cast

import pytest
from grpc import aio

from cortex_core import ScheduledItem, ScheduleKind
from cortex_seam import (
    SEAM_TOKEN_HEADER,
    AckReminderReply,
    AckReminderRequest,
    BrainServiceStub,
    DueReminder,
    ListDueRemindersReply,
    ListDueRemindersRequest,
)
from cortex_session import DEFAULT_REDIS_URL, RedisScheduleStore

_SEAM_ENDPOINT = os.environ.get("CORTEX_SEAM_ENDPOINT", "127.0.0.1:50051")
# The default CORTEX_SCHEDULE_POLL_S is 5.0; wait out at least two passes with margin.
_ATTEMPTS = 40
_RETRY_S = 0.5


def _metadata() -> tuple[tuple[str, str], ...] | None:
    token = os.environ.get("CORTEX_SEAM_TOKEN", "")
    return ((SEAM_TOKEN_HEADER, token),) if token else None


async def _list(stub: BrainServiceStub) -> ListDueRemindersReply:
    method = stub.ListDueReminders  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast(
        "ListDueRemindersReply", await method(ListDueRemindersRequest(), metadata=_metadata())
    )


async def _ack(stub: BrainServiceStub, reminder_id: str) -> AckReminderReply:
    method = stub.AckReminder  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast(
        "AckReminderReply",
        await method(AckReminderRequest(reminder_id=reminder_id), metadata=_metadata()),
    )


async def _wait_for_fire(stub: BrainServiceStub, item_id: str) -> DueReminder | None:
    for _ in range(_ATTEMPTS):
        reply = await _list(stub)
        fired = [r for r in reply.reminders if r.reminder_id == item_id]
        if fired:
            return fired[0]
        await asyncio.sleep(_RETRY_S)
    return None


@pytest.mark.integration
async def test_reminder_fires_and_round_trips_over_the_live_seam() -> None:
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
        async with aio.insecure_channel(_SEAM_ENDPOINT) as channel:
            stub = BrainServiceStub(channel)
            fired = await _wait_for_fire(stub, item_id)
            assert fired is not None, "the ticker did not fire the seeded reminder in time"
            assert fired.text == "live fire proof"
            assert fired.recurring is False
            assert fired.tainted is False
            assert fired.session_id == "live-seam"
            assert (await _ack(stub, item_id)).acked is True
            # Delivered: gone from the pull view, and a second ack is a no-op.
            assert [r for r in (await _list(stub)).reminders if r.reminder_id == item_id] == []
            assert (await _ack(stub, item_id)).acked is False
    finally:
        await store.cancel(item_id)  # a leftover on failure; acked success already deleted it
        await store.aclose()
