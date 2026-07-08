"""The InMemoryBodyGateway's notify surface (ADR-0025); volume paths: test_fakes/test_volume."""

import pytest

from cortex_core import BodyGatewayError, InMemoryBodyGateway, SentNotification


async def test_notify_records_the_toast_and_answers_shown() -> None:
    gateway = InMemoryBodyGateway()
    shown = await gateway.notify(title="Reminder", body="stretch", reminder_id="r1", tainted=True)
    assert shown is True
    assert gateway.notifications == (
        SentNotification(title="Reminder", body="stretch", reminder_id="r1", tainted=True),
    )


async def test_notify_shown_false_scripts_a_declining_body() -> None:
    gateway = InMemoryBodyGateway(shown=False)
    assert await gateway.notify(title="t", body="b", reminder_id="r1") is False
    assert len(gateway.notifications) == 1


async def test_notify_raises_the_scripted_failure() -> None:
    gateway = InMemoryBodyGateway(fail=BodyGatewayError("unreachable"))
    with pytest.raises(BodyGatewayError, match="unreachable"):
        await gateway.notify(title="t", body="b", reminder_id="r1")
    assert gateway.notifications == ()
