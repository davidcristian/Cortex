"""The InMemoryBodyGateway's notify and capture surfaces (ADR-0025/0029); volume paths:
test_fakes/test_volume."""

from datetime import UTC, datetime

import pytest

from cortex_core import (
    BodyGatewayError,
    CaptureAsk,
    ImagePart,
    InMemoryBodyGateway,
    ScreenCapture,
    SentNotification,
    default_capture,
)


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


async def test_capture_screen_records_the_hints_and_answers_the_default() -> None:
    gateway = InMemoryBodyGateway()
    capture = await gateway.capture_screen(max_edge=1600, max_bytes=6291456)
    assert gateway.captures == (CaptureAsk(max_edge=1600, max_bytes=6291456),)
    assert capture.image.mime_type == "image/png"
    assert (capture.image.width, capture.image.height) == (1, 1)
    assert capture.captured_at.tzinfo is not None


async def test_capture_screen_answers_a_scripted_capture() -> None:
    scripted = ScreenCapture(
        image=ImagePart(data=b"\x89PNG", mime_type="image/png", width=800, height=600),
        source_width=1600,
        source_height=1200,
        captured_at=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
    )
    gateway = InMemoryBodyGateway(capture=scripted)
    assert await gateway.capture_screen() == scripted
    assert gateway.captures == (CaptureAsk(max_edge=0, max_bytes=0),)


async def test_capture_screen_raises_the_scripted_failure() -> None:
    gateway = InMemoryBodyGateway(fail=BodyGatewayError("unreachable"))
    with pytest.raises(BodyGatewayError, match="unreachable"):
        await gateway.capture_screen()
    assert gateway.captures == ()


def test_the_default_capture_reports_a_downscaled_view() -> None:
    # The fake's stand-in is deliberately a 1x1 view of a 2x2 screen, so a consumer that only
    # ever sees the default still exercises the downscaled branch of the value.
    assert default_capture().downscaled is True
