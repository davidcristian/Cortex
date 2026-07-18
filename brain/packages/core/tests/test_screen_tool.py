"""Behaviour tests for the capture_screen built-in and the pixel boundary it stands on
(ADR-0029): the spec, the stand-in text, the trust stamps, and the inheritance that matters
most, which is that a capture taints the turn through the ordinary machinery so the existing
gated-call denial applies with no new special case.
"""

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from cortex_core import (
    CAPTURE_SCREEN_TOOL_NAME,
    DENIED_MSG,
    MAX_IDENTICAL_DISPATCHES,
    BodyGatewayError,
    CaptureScreenTool,
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
    *, width: int = 1600, height: int = 900, source: tuple[int, int] = (2560, 1440)
) -> ScreenCapture:
    return ScreenCapture(
        image=ImagePart(data=_PNG, mime_type="image/png", width=width, height=height),
        source_width=source[0],
        source_height=source[1],
        captured_at=datetime(2026, 7, 25, 10, 14, 3, tzinfo=UTC),
    )


def _call() -> ToolCall:
    return ToolCall(id="c1", name=CAPTURE_SCREEN_TOOL_NAME, arguments={})


async def _send(_arguments: Mapping[str, object]) -> str:
    return "sent"


def _email_dispatcher(confirmer: RecordingConfirmer) -> tuple[ToolDispatcher, RecordingAuditSink]:
    """A dispatcher over one gated tool, the shape both gate arms below drive."""
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


async def test_the_spec_is_ungated_and_takes_no_arguments() -> None:
    tool = CaptureScreenTool(InMemoryBodyGateway())
    spec = tool.spec
    assert spec.name == "capture_screen"
    assert spec.gated is False
    assert spec.parameters["properties"] == {}


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


async def test_an_unreachable_body_is_a_trusted_error_with_no_pixels() -> None:
    # Deliberately asymmetric: nothing untrusted arrived, so tainting here would close the
    # user's gated tools for the rest of a turn in which nothing was read.
    body = InMemoryBodyGateway(fail=BodyGatewayError("body down"))
    result = await CaptureScreenTool(body).invoke(_call())

    assert result.is_error is True
    assert result.trust is Trust.TRUSTED
    assert result.images == ()
    assert result.content == "could not reach the body to capture the screen: body down"


async def test_a_capture_taints_the_turn_through_the_ordinary_ledger() -> None:
    ledger = TaintLedger()
    body = InMemoryBodyGateway(capture=_capture())
    result = await CaptureScreenTool(body).invoke(_call())

    assert ledger.tainted is False
    ledger.observe(result)
    assert ledger.tainted is True


async def test_a_failed_capture_leaves_the_turn_clean() -> None:
    ledger = TaintLedger()
    body = InMemoryBodyGateway(fail=BodyGatewayError("body down"))
    ledger.observe(await CaptureScreenTool(body).invoke(_call()))
    assert ledger.tainted is False


async def test_a_gated_call_after_a_capture_is_denied_without_asking_the_user() -> None:
    """The inheritance this whole slice rests on, proven rather than assumed.

    A screen injection is transcribed verbatim by the model even under a hardened preamble, so
    the boundary cannot be prompt-shaped. It is this: the capture marks the turn through the
    same ledger every other untrusted result uses, and the dispatcher then hard-denies a gated
    call, never reaching the confirmer. The confirmer here would **approve**, so an approving
    confirmer cannot mask the block: if the capture ever stopped tainting, this test would see
    the call go through.
    """
    confirmer = RecordingConfirmer(answer=True)
    dispatcher, audit = _email_dispatcher(confirmer)
    ledger = TaintLedger()

    body = InMemoryBodyGateway(capture=_capture())
    ledger.observe(await CaptureScreenTool(body).invoke(_call()))

    # The turn's stamp is a dispatch keyword, not a field the call carries: the dispatcher
    # overwrites a call-borne stamp precisely so a model-forged one feeds nothing. This is how
    # the tool loop passes it, rebuilt per dispatch, which is what makes the bit flip mid-loop.
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
    """The control arm: without the capture the very same call reaches the confirmer and runs,
    so the test above is measuring the taint and not some unrelated refusal."""
    confirmer = RecordingConfirmer(answer=True)
    dispatcher, _audit = _email_dispatcher(confirmer)

    allowed = await dispatcher.dispatch(
        ToolCall(id="c2", name="send_email", arguments={"to": "x@example.com"}),
        stamp=TurnStamp(tainted=False),
    )

    assert allowed.is_error is False
    assert [request.tool_name for request in confirmer.requests] == ["send_email"]


async def test_the_audit_line_carries_no_image_bytes_on_either_path() -> None:
    """Pixels ride beside ``content``, never inside it, so the audit trail stays text."""
    for body in (
        InMemoryBodyGateway(capture=_capture()),
        InMemoryBodyGateway(fail=BodyGatewayError("body down")),
    ):
        result = await CaptureScreenTool(body).invoke(_call())
        assert _PNG not in result.content.encode()


async def test_two_identical_captures_are_all_a_turn_gets() -> None:
    """No new counter: the spec takes no arguments, so every call is byte-identical and the
    existing identical-dispatch cap bounds captures per turn for free."""
    salience = RepeatSalience()
    rounds: list[list[ToolCall]] = []
    admitted: list[bool] = []
    for _ in range(3):
        rounds.append([])
        verdict = salience.admits(_call(), rounds)
        admitted.append(verdict)
        if verdict:
            rounds[-1].append(_call())
    assert admitted == [True, True, False]
    assert MAX_IDENTICAL_DISPATCHES == 2


def test_the_tool_name_is_the_one_the_owner_puts_in_the_gated_list() -> None:
    # The documented zero-code opt-in is CORTEX_TOOLS_GATED=send_email,capture_screen, so the
    # advertised name has to be exactly this string.
    assert CAPTURE_SCREEN_TOOL_NAME == "capture_screen"


@pytest.mark.parametrize("mime", ["image/png", "image/jpeg"])
async def test_the_tool_passes_the_bodys_encoding_through_untouched(mime: str) -> None:
    # The body may swap encoders behind the seam; nothing here re-encodes or re-checks pixels.
    capture = ScreenCapture(
        image=ImagePart(data=_PNG, mime_type=mime, width=64, height=64),
        source_width=64,
        source_height=64,
        captured_at=datetime(2026, 7, 25, tzinfo=UTC),
    )
    result = await CaptureScreenTool(InMemoryBodyGateway(capture=capture)).invoke(_call())
    assert result.images[0].mime_type == mime
