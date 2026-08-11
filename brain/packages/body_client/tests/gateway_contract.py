"""The `BodyGateway` contract, run over every implementation (AGENTS.md: ports before adapters).

Nine checks over the four verbs the port has. They are the description the volume, reminder and
screen tools are written against: each of those turns a gateway answer into a sentence the cortex
reads, and a gateway that answered the ask instead of the outcome would make every one of those
sentences a guess.

Each fixture supplies the conditions of the world no method of the port can create. The body
declines a notification, the body goes away, and the body answers a **fixed** capture this file
names, larger than one pixel and pointed at the display, which is what lets a check ask for a
focus capture and a bound the answer breaks. Two readers say what the body received, since the
port's own promises about what crosses the seam (a taint bit, a bound asked for, a capture
attempted exactly once) are otherwise invisible from the answer.
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from cortex_core import (
    BodyGateway,
    BodyGatewayError,
    CaptureAsk,
    CaptureTarget,
    ImagePart,
    ScreenCapture,
    SentNotification,
)

# A four-pixel PNG. Bigger than one pixel on purpose: a bound check needs a capture that can be
# over a bound, and a one-pixel picture is under every bound worth asking for.
_SQUARE_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000002000000020802000000fdd49a"
    "730000001849444154789c6360a03d00006c0018f4b1a5ea0000000049454e44ae426082"
)

# The capture every fixture's body answers, whatever it is asked for. It is a DISPLAY picture, so
# a check can ask for FOCUS and read back what the body actually pointed at.
CONTRACT_CAPTURE = ScreenCapture(
    image=ImagePart(data=_SQUARE_PNG, mime_type="image/png", width=2, height=2),
    source_width=8,
    source_height=8,
    captured_at=datetime(2026, 8, 11, 9, 30, tzinfo=UTC),
    target=CaptureTarget.DISPLAY,
)


@dataclass(frozen=True, slots=True)
class GatewayUnderTest:
    """One implementation, the two ways a check may change the body, and what the body heard."""

    gateway: BodyGateway
    decline_notifications: Callable[[], None]
    break_body: Callable[[], None]
    notifications: Callable[[], Sequence[SentNotification]]
    captures: Callable[[], Sequence[CaptureAsk]]


type Check = Callable[[GatewayUnderTest], Awaitable[None]]


async def volume_reads_back_the_state_the_body_holds(under_test: GatewayUnderTest) -> None:
    """A read reports the host's own state, both fields of it."""
    await under_test.gateway.set_volume(level=0.25, mute=True)
    state = await under_test.gateway.get_volume()
    assert (state.level, state.muted) == (0.25, True)


async def a_write_touches_only_the_field_it_was_given(under_test: GatewayUnderTest) -> None:
    """An unset field is left alone, which is the whole reason both are optional.

    "Mute it" must not also reset the level, and "set it to a half" must not also unmute. On the
    wire that is proto explicit presence, and an adapter sending a zero for an absent level would
    silence the host on every mute; in the fake it is the ``is not None`` beside it. The two are
    different mechanisms for one promise, which is exactly what a shared check is for.

    Every level in this file is exact in 32 bits, because the wire carries a ``float`` where the
    fake keeps a Python one. That divergence is real and the list stays above it: what both
    implementations owe is which field moved, not how many bits of the number survived the trip.
    """
    await under_test.gateway.set_volume(level=0.5, mute=False)
    muted = await under_test.gateway.set_volume(mute=True)
    assert (muted.level, muted.muted) == (0.5, True)
    lowered = await under_test.gateway.set_volume(level=0.125)
    assert (lowered.level, lowered.muted) == (0.125, True)


async def a_write_reports_the_state_after_it(under_test: GatewayUnderTest) -> None:
    """The answer is ground truth, never the ask echoed back.

    The volume tool reads its sentence off this value, so an implementation replying with what it
    was asked for would report a change the host refused as though it had happened.
    """
    written = await under_test.gateway.set_volume(level=0.75, mute=False)
    assert written == await under_test.gateway.get_volume()


async def a_level_outside_the_range_comes_back_inside_it(under_test: GatewayUnderTest) -> None:
    """The port's range is [0.0, 1.0] and something on the path holds it, whichever end.

    The check is about the path rather than about who does it: the fake clamps where it stands and
    the adapter's answer is clamped by the body (the Windows backend's own rule). Either way a
    model asking for 3.0 gets a legal state back, and the caller never has to know which.
    """
    loud = await under_test.gateway.set_volume(level=3.0)
    assert loud.level == 1.0
    silent = await under_test.gateway.set_volume(level=-2.0)
    assert silent.level == 0.0


async def a_notification_reaches_the_body_verbatim_taint_included(
    under_test: GatewayUnderTest,
) -> None:
    """Every field crosses, and the taint bit crosses with them.

    ``tainted`` is what tells the body to badge the text and render it inert, so a gateway that
    dropped it would hand attacker-influenced words to the host as though the brain had written
    them. It is the one field on this port whose loss is silent.
    """
    shown = await under_test.gateway.notify(
        title="Reminder", body="stand up", reminder_id="r-1", tainted=True
    )
    assert shown is True
    assert list(under_test.notifications()) == [
        SentNotification(title="Reminder", body="stand up", reminder_id="r-1", tainted=True)
    ]


async def a_declined_notification_is_an_answer_rather_than_an_error(
    under_test: GatewayUnderTest,
) -> None:
    """A body that was reached and said no answers False; it does not raise.

    The ticker reads that boolean and leaves the reminder deliverable for the pull path. An
    implementation raising here would turn "notifications are switched off" into a failed tick.
    """
    under_test.decline_notifications()
    assert await under_test.gateway.notify(title="t", body="b", reminder_id="r-2") is False


async def a_capture_reports_what_the_body_pointed_at_not_what_was_asked(
    under_test: GatewayUnderTest,
) -> None:
    """The target on the answer is the body's reading, and the ask still reaches the body.

    A crop and a shrunk screen are the same blob, so this is the one thing about a capture the
    caller cannot re-derive from the pixels. The receipt the user sees is picked from it, so a
    gateway echoing the ask would tell the user a window was photographed when the screen was.
    """
    capture = await under_test.gateway.capture_screen(target=CaptureTarget.FOCUS)
    assert capture.target is CaptureTarget.DISPLAY
    assert capture.image.width == CONTRACT_CAPTURE.image.width
    assert [ask.target for ask in under_test.captures()] == [CaptureTarget.FOCUS]


async def a_capture_over_the_bound_it_asked_for_is_refused(under_test: GatewayUnderTest) -> None:
    """A non-zero bound is a bound on the reply, not a hint that may be quietly overrun.

    A bound is what this deployment decided a turn may spend on pixels, and it is only ever a
    request on the way out: an older body ignores a field it does not know and answers full size.
    So every implementation of this port re-verifies on receipt, and a picture over the bound is
    refused rather than handed to a turn that was told not to spend it.
    """
    try:
        await under_test.gateway.capture_screen(max_edge=1)
    except BodyGatewayError:
        pass
    else:
        msg = "a capture over the edge it asked for was handed back"
        raise AssertionError(msg)
    try:
        await under_test.gateway.capture_screen(max_bytes=1)
    except BodyGatewayError:
        return
    msg = "a capture over the byte budget it asked for was handed back"
    raise AssertionError(msg)


async def a_capture_is_attempted_exactly_once(under_test: GatewayUnderTest) -> None:
    """One ask, one photograph. A retry would picture a different screen.

    The port says this rather than leaving it to whoever writes the next retry decorator: a repeat
    neither reproduces the answer nor leaves the world unchanged, and it fires a second host
    receipt for one user intent.
    """
    await under_test.gateway.capture_screen(max_edge=64, max_bytes=4096)
    assert list(under_test.captures()) == [
        CaptureAsk(max_edge=64, max_bytes=4096, target=CaptureTarget.DISPLAY)
    ]


async def a_body_that_has_gone_away_fails_every_verb(under_test: GatewayUnderTest) -> None:
    """One error type for the whole port, so a caller has one thing to catch.

    The volume and capture tools catch ``BodyGatewayError`` and word a recoverable result from it.
    Anything else escaping a verb kills the turn instead of failing the action.
    """
    under_test.break_body()
    attempts: Sequence[Callable[[], Awaitable[object]]] = (
        under_test.gateway.get_volume,
        lambda: under_test.gateway.set_volume(mute=True),
        lambda: under_test.gateway.notify(title="t", body="b", reminder_id="r-3"),
        under_test.gateway.capture_screen,
    )
    for attempt in attempts:
        try:
            await attempt()
        except BodyGatewayError:
            continue
        msg = "a body that has gone away answered anyway"
        raise AssertionError(msg)


ALL_CHECKS: Sequence[Check] = (
    volume_reads_back_the_state_the_body_holds,
    a_write_touches_only_the_field_it_was_given,
    a_write_reports_the_state_after_it,
    a_level_outside_the_range_comes_back_inside_it,
    a_notification_reaches_the_body_verbatim_taint_included,
    a_declined_notification_is_an_answer_rather_than_an_error,
    a_capture_reports_what_the_body_pointed_at_not_what_was_asked,
    a_capture_over_the_bound_it_asked_for_is_refused,
    a_capture_is_attempted_exactly_once,
    a_body_that_has_gone_away_fails_every_verb,
)
