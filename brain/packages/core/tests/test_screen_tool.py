from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from cortex_core import (
    CAPTURE_SCREEN_TOOL_NAME,
    DENIED_MSG,
    MAX_IDENTICAL_DISPATCHES,
    BodyFailure,
    BodyGatewayError,
    CaptureBounds,
    CaptureScreenTool,
    CaptureTarget,
    DispatchPolicy,
    ImagePart,
    InMemoryBodyGateway,
    InMemoryToolRegistry,
    RecordingAuditSink,
    RecordingConfirmer,
    RepeatSalience,
    ScreenCapture,
    SystemClock,
    TaintLedger,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    Trust,
    TurnStamp,
)

_PNG = b"\x89PNG\r\n\x1a\n"


def _capture(
    *,
    width: int = 1600,
    height: int = 900,
    source: tuple[int, int] = (2560, 1440),
    target: CaptureTarget = CaptureTarget.DISPLAY,
) -> ScreenCapture:
    return ScreenCapture(
        image=ImagePart(data=_PNG, mime_type="image/png", width=width, height=height),
        source_width=source[0],
        source_height=source[1],
        captured_at=datetime(2026, 7, 25, 10, 14, 3, tzinfo=UTC),
        target=target,
    )


def _call(target: str = "display") -> ToolCall:
    return ToolCall(id="c1", name=CAPTURE_SCREEN_TOOL_NAME, arguments={"target": target})


async def _send(_arguments: Mapping[str, object]) -> str:
    return "sent"


def _email_dispatcher(confirmer: RecordingConfirmer) -> tuple[ToolDispatcher, RecordingAuditSink]:
    """A dispatcher over one tool that needs approval, used by both cases below."""
    spec = ToolSpec(name="send_email", description="send", parameters={}, gated=True)
    audit = RecordingAuditSink()
    dispatcher = ToolDispatcher(
        InMemoryToolRegistry({"send_email": (spec, _send)}),
        audit,
        SystemClock(),
        confirmer=confirmer,
        policy=DispatchPolicy(gated_names=frozenset({"send_email"})),
    )
    return dispatcher, audit


async def test_the_spec_is_ungated_and_makes_the_model_name_a_target() -> None:
    tool = CaptureScreenTool(InMemoryBodyGateway())
    spec = tool.spec
    assert spec.name == "capture_screen"
    assert spec.gated is False
    assert spec.parameters["required"] == ["target"]


def test_the_vocabulary_the_model_sees_is_the_vocabulary_the_seam_carries() -> None:
    schema = CaptureScreenTool(InMemoryBodyGateway()).spec.parameters
    target = schema["properties"]["target"]
    assert target["enum"] == [member.value for member in CaptureTarget]
    assert target["enum"] == ["display", "focus"]


def test_the_steer_promises_only_what_the_window_crop_measurement_supports() -> None:
    spec = CaptureScreenTool(InMemoryBodyGateway()).spec
    help_text = str(spec.parameters["properties"]["target"]["description"])

    for text in (spec.description, help_text):
        assert "full detail" not in text, "a window past the edge is resampled like the screen"
        assert "small text" in text, "the one case the crop measurably wins"
    assert "nothing outside that window is in the picture" in spec.description
    assert "too large to send whole is shrunk exactly as the screen is" in spec.description
    assert "nothing outside it is captured" in help_text
    assert "ask again with 'display'" in spec.description


async def test_a_capture_is_untrusted_and_carries_exactly_one_image() -> None:
    body = InMemoryBodyGateway(capture=_capture())
    result = await CaptureScreenTool(body).invoke(_call())

    assert result.trust is Trust.UNTRUSTED
    assert result.is_error is False
    assert len(result.images) == 1
    assert result.images[0].data == _PNG


async def test_the_stand_in_text_names_the_sizes_and_the_time_and_nothing_else() -> None:
    body = InMemoryBodyGateway(capture=_capture())
    result = await CaptureScreenTool(body).invoke(_call())

    assert result.content == (
        "screen capture of the primary display: 1600x900 image/png, "
        "downscaled from 2560x1440, taken at 2026-07-25T10:14:03+00:00. "
        "The picture is attached to this message as an image part; it cannot be fenced as text."
    )


async def test_a_capture_at_the_display_size_says_nothing_about_downscaling() -> None:
    body = InMemoryBodyGateway(capture=_capture(width=800, height=600, source=(800, 600)))
    result = await CaptureScreenTool(body).invoke(_call())
    assert "downscaled" not in result.content
    assert result.content.startswith("screen capture of the primary display: 800x600 image/png,")


async def test_the_configured_bounds_reach_the_body() -> None:
    body = InMemoryBodyGateway(capture=_capture())
    await CaptureScreenTool(body, max_edge=1280, max_bytes=4096).invoke(_call())
    assert [(ask.max_edge, ask.max_bytes) for ask in body.captures] == [(1280, 4096)]


async def test_the_target_the_model_named_reaches_the_body() -> None:
    body = InMemoryBodyGateway(capture=_capture())
    tool = CaptureScreenTool(body)
    await tool.invoke(_call("focus"))
    await tool.invoke(_call("display"))
    assert [ask.target for ask in body.captures] == [CaptureTarget.FOCUS, CaptureTarget.DISPLAY]


async def test_a_window_capture_is_described_as_a_crop_and_not_as_a_shrunk_screen() -> None:
    windowed = _capture(width=1720, height=1200, target=CaptureTarget.FOCUS)
    result = await CaptureScreenTool(InMemoryBodyGateway(capture=windowed)).invoke(_call("focus"))

    assert result.content == (
        "screen capture of one window, cropped out of the 2560x1440 primary display: "
        "1720x1200 image/png, taken at 2026-07-25T10:14:03+00:00. "
        "The rest of the screen was not captured. "
        "The picture is attached to this message as an image part; it cannot be fenced as text."
    )
    assert "downscaled" not in result.content


async def test_a_window_that_filled_the_screen_is_described_as_the_screen() -> None:
    body = InMemoryBodyGateway(capture=_capture(target=CaptureTarget.DISPLAY))
    result = await CaptureScreenTool(body).invoke(_call("focus"))

    assert result.content.startswith("screen capture of the primary display: 1600x900 image/png,")
    assert [ask.target for ask in body.captures] == [CaptureTarget.FOCUS]


async def test_a_capture_with_no_target_is_refused_without_taking_a_picture() -> None:
    body = InMemoryBodyGateway(capture=_capture())
    result = await CaptureScreenTool(body).invoke(
        ToolCall(id="c1", name=CAPTURE_SCREEN_TOOL_NAME, arguments={})
    )

    assert result.is_error is True
    assert result.trust is Trust.TRUSTED
    assert result.images == ()
    assert result.content.startswith("capture_screen requires 'target'")
    assert list(body.captures) == [], "nothing was captured, so nothing may taint the turn"


@pytest.mark.parametrize("named", ["window", "DISPLAY", "", "focus "])
async def test_a_target_outside_the_vocabulary_is_a_tool_error_and_never_a_raise(
    named: str,
) -> None:
    body = InMemoryBodyGateway(capture=_capture())
    result = await CaptureScreenTool(body).invoke(_call(named))

    assert result.is_error is True
    assert result.trust is Trust.TRUSTED
    assert result.content == "'target' must be one of: display, focus"
    assert list(body.captures) == []


async def test_a_target_that_is_not_a_string_is_refused_like_a_missing_one() -> None:
    body = InMemoryBodyGateway(capture=_capture())
    result = await CaptureScreenTool(body).invoke(
        ToolCall(id="c1", name=CAPTURE_SCREEN_TOOL_NAME, arguments={"target": 1})
    )

    assert result.is_error is True
    assert result.content.startswith("capture_screen requires 'target'")
    assert list(body.captures) == []


async def test_an_unreachable_body_is_a_trusted_error_with_no_pixels() -> None:
    body = InMemoryBodyGateway(fail=BodyGatewayError("body down", kind=BodyFailure.UNREACHABLE))
    result = await CaptureScreenTool(body).invoke(_call())

    assert result.is_error is True
    assert result.trust is Trust.TRUSTED
    assert result.images == ()
    assert result.content == "could not reach the body to capture the screen: body down"


async def test_the_shipping_default_reads_as_a_refusal_and_not_as_a_dead_body() -> None:
    disabled = BodyGatewayError(
        "body capture_screen failed: screen capture is disabled on this host",
        kind=BodyFailure.REFUSED,
    )
    result = await CaptureScreenTool(InMemoryBodyGateway(fail=disabled)).invoke(_call())

    assert result.content == (
        "the body refused to capture the screen: body capture_screen failed: "
        "screen capture is disabled on this host"
    )
    assert "could not reach the body" not in result.content


async def test_a_capture_too_large_to_send_is_not_reported_as_a_broken_backend() -> None:
    oversize = BodyGatewayError(
        "body capture_screen failed: the capture is too large to send to the brain: 6291457 bytes",
        kind=BodyFailure.OVERSIZE,
    )
    result = await CaptureScreenTool(InMemoryBodyGateway(fail=oversize)).invoke(_call())

    assert result.content.startswith(
        "the body could not capture the screen within the size the gRPC link allows:"
    )
    assert result.trust is Trust.TRUSTED
    assert result.images == ()


async def test_a_capture_taints_the_turn_through_the_ordinary_ledger() -> None:
    ledger = TaintLedger()
    body = InMemoryBodyGateway(capture=_capture())
    result = await CaptureScreenTool(body).invoke(_call())

    assert ledger.tainted is False
    ledger.observe(result)
    assert ledger.tainted is True


def test_the_default_bounds_ask_the_body_for_its_own_defaults() -> None:
    # Zero means "your own default" on the wire, not "no bound": proto3 cannot tell an unset
    # uint32 from an explicit zero. Written as literals so a changed default fails here.
    assert (CaptureBounds().max_edge, CaptureBounds().max_bytes) == (0, 0)


async def test_a_failed_capture_leaves_the_turn_clean() -> None:
    ledger = TaintLedger()
    body = InMemoryBodyGateway(fail=BodyGatewayError("body down"))
    ledger.observe(await CaptureScreenTool(body).invoke(_call()))
    assert ledger.tainted is False


async def test_a_gated_call_after_a_capture_is_denied_without_asking_the_user() -> None:
    confirmer = RecordingConfirmer(answer=True)
    dispatcher, audit = _email_dispatcher(confirmer)
    ledger = TaintLedger()

    body = InMemoryBodyGateway(capture=_capture())
    ledger.observe(await CaptureScreenTool(body).invoke(_call()))

    blocked = await dispatcher.dispatch(
        ToolCall(id="c2", name="send_email", arguments={"to": "x@example.com"}),
        stamp=TurnStamp(tainted=ledger.tainted),
    )

    assert blocked.is_error is True
    assert blocked.content == DENIED_MSG
    assert list(confirmer.requests) == [], "a hard denial must never reach the confirmer"
    assert [(line.name, line.ok, line.detail) for line in audit.records] == [
        ("send_email", False, DENIED_MSG)
    ], "the denial is audited like any other dispatch"


async def test_the_same_gated_call_is_confirmed_when_nothing_was_captured() -> None:
    confirmer = RecordingConfirmer(answer=True)
    dispatcher, _audit = _email_dispatcher(confirmer)

    allowed = await dispatcher.dispatch(
        ToolCall(id="c2", name="send_email", arguments={"to": "x@example.com"}),
        stamp=TurnStamp(tainted=False),
    )

    assert allowed.is_error is False
    assert [request.tool_name for request in confirmer.requests] == ["send_email"]


async def test_the_audit_line_carries_no_image_bytes_on_either_path() -> None:
    for body in (
        InMemoryBodyGateway(capture=_capture()),
        InMemoryBodyGateway(fail=BodyGatewayError("body down")),
    ):
        result = await CaptureScreenTool(body).invoke(_call())
        assert _PNG not in result.content.encode()


async def test_two_captures_per_target_is_what_a_loop_gets_now() -> None:
    salience = RepeatSalience()
    rounds: list[list[ToolCall]] = []
    admitted: list[tuple[str, bool]] = []
    for _round in range(3):
        rounds.append([])
        for target in ("display", "focus"):
            verdict = salience.admits(_call(target), rounds)
            admitted.append((target, verdict))
            if verdict:
                rounds[-1].append(_call(target))

    assert admitted == [
        ("display", True),
        ("focus", True),
        ("display", True),
        ("focus", True),
        ("display", False),
        ("focus", False),
    ]
    assert sum(1 for _target, verdict in admitted if verdict) == 2 * MAX_IDENTICAL_DISPATCHES
    assert MAX_IDENTICAL_DISPATCHES == 2


async def test_a_second_identical_target_in_one_round_is_refused_outright() -> None:
    salience = RepeatSalience()
    first_round: list[list[ToolCall]] = [[]]

    assert salience.admits(_call("focus"), first_round) is True
    first_round[-1].append(_call("focus"))
    assert salience.admits(_call("focus"), first_round) is False
    assert salience.admits(_call("display"), first_round) is True


def test_the_tool_name_is_the_one_the_owner_puts_in_the_gated_list() -> None:
    # The documented opt-in is CORTEX_TOOLS_GATED=send_email,capture_screen, so the advertised
    # name has to be exactly this string.
    assert CAPTURE_SCREEN_TOOL_NAME == "capture_screen"


@pytest.mark.parametrize("mime", ["image/png", "image/jpeg"])
async def test_the_tool_passes_the_bodys_encoding_through_untouched(mime: str) -> None:
    capture = ScreenCapture(
        image=ImagePart(data=_PNG, mime_type=mime, width=64, height=64),
        source_width=64,
        source_height=64,
        captured_at=datetime(2026, 7, 25, tzinfo=UTC),
    )
    result = await CaptureScreenTool(InMemoryBodyGateway(capture=capture)).invoke(_call())
    assert result.images[0].mime_type == mime
