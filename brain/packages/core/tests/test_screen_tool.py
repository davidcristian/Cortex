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


async def test_the_spec_is_ungated_and_makes_the_model_name_a_target() -> None:
    tool = CaptureScreenTool(InMemoryBodyGateway())
    spec = tool.spec
    assert spec.name == "capture_screen"
    assert spec.gated is False
    assert spec.parameters["required"] == ["target"]


def test_the_vocabulary_the_model_sees_is_the_vocabulary_the_seam_carries() -> None:
    """The one half of the enum coupling a gate can hold, held.

    The schema's strings are derived from ``CaptureTarget`` rather than restated beside it, so a
    third target cannot reach the wire while the model is still offered two. The other half,
    these members against the proto's, is generated on both sides and no scan can parse it; it
    is recorded in docs/refinements/repo-gates.md instead.
    """
    schema = CaptureScreenTool(InMemoryBodyGateway()).spec.parameters
    target = schema["properties"]["target"]
    assert target["enum"] == [member.value for member in CaptureTarget]
    assert target["enum"] == ["display", "focus"]


def test_the_steer_promises_only_what_the_window_crop_measurement_supports() -> None:
    """The description is a model-facing contract, so it is held to the measurement.

    A window crop is a large win on the smallest text (15 px goes 5 of 12 to 9 or 10 of 12) and a
    loss over a whole desktop (29 to 31 of 47 against 32 to 33), because it cannot see past its
    window. And the detail it buys is being **unresampled**, not being cropped, so it is
    conditional on the window fitting the capture edge, which neither the model nor this tool can
    check. Three properties follow and are pinned on **both** places the steer is spelled, the
    description and the schema's own help, since a copy left behind is a lie the model still
    reads: no unconditional promise of full detail, the cost of a window said out loud, and the
    one recovery the model can act on kept.
    """
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
    """The reply's own answer picks the sentence, so the model is never told about a desktop it
    was not shown. A window fitting the capture edge was not resampled at all, and even one that
    was is not a view of the whole 2560x1440 display."""
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
    """The body reads the reply's target off what it encoded rather than off the ask, and the
    receipt the user sees is picked by the same predicate, so a maximised window cannot make the
    two surfaces disagree. Asking for the window and being told "display" is not a failure."""
    body = InMemoryBodyGateway(capture=_capture(target=CaptureTarget.DISPLAY))
    result = await CaptureScreenTool(body).invoke(_call("focus"))

    assert result.content.startswith("screen capture of the primary display: 1600x900 image/png,")
    assert [ask.target for ask in body.captures] == [CaptureTarget.FOCUS]


async def test_a_capture_with_no_target_is_refused_without_taking_a_picture() -> None:
    """Refused rather than defaulted, and the reason is not tidiness.

    The default it would take is the whole screen, which is the more exposing of the two
    pictures, and widening silently on a question the model never said was about the whole screen
    is the wrong direction. (The legibility leg this used to lean on as well narrowed under the
    window-crop measurement: the shrunk screen reads more of a desktop than a crop does, and only
    the smallest text goes the other way.) And a spelling that captures is worth two captures to a
    loop, so the empty call taking none is what keeps the ceiling at two per target.
    """
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
    """The model chose it and the model can correct it, so this is a result rather than an
    exception that would kill the turn. The match is exact on purpose: accepting ``DISPLAY``
    beside ``display`` would add a whole call identity that takes pictures."""
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
    # Deliberately asymmetric: nothing untrusted arrived, so tainting here would close the
    # user's gated tools for the rest of a turn in which nothing was read.
    body = InMemoryBodyGateway(fail=BodyGatewayError("body down", kind=BodyFailure.UNREACHABLE))
    result = await CaptureScreenTool(body).invoke(_call())

    assert result.is_error is True
    assert result.trust is Trust.TRUSTED
    assert result.images == ()
    assert result.content == "could not reach the body to capture the screen: body down"


async def test_the_shipping_default_reads_as_a_refusal_and_not_as_a_dead_body() -> None:
    """The one row of the failure table an untouched install actually hits.

    With ``CORTEX_HOST_CAPTURE`` unset the body answers ``PERMISSION_DENIED`` at once, and this
    used to reach the model as ``could not reach the body to capture the screen``, with the truth
    appended after a colon. A capture the host switched off is not a capture nobody could reach,
    and telling the model otherwise sends the user to check a body that is running fine.
    """
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
    """The other half of the same defect: a picture that was taken and will not fit is a
    different thing from a body whose backend broke, and the two used to be one sentence behind
    one status code."""
    oversize = BodyGatewayError(
        "body capture_screen failed: the capture is too large for the seam: 6291457 bytes",
        kind=BodyFailure.OVERSIZE,
    )
    result = await CaptureScreenTool(InMemoryBodyGateway(fail=oversize)).invoke(_call())

    assert result.content.startswith(
        "the body could not capture the screen within the size the seam allows:"
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
    # Zero is not "no bound", it is "your default" on the wire (proto3 cannot tell an unset
    # uint32 from an explicit zero), and the brain then holds the reply to the domain ceiling
    # alone. Pinned against literals: a default quietly moved to 640 or to a byte budget would
    # otherwise change what every deployment asks for with nothing red.
    assert (CaptureBounds().max_edge, CaptureBounds().max_bytes) == (0, 0)


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


async def test_two_captures_per_target_is_what_a_loop_gets_now() -> None:
    """The bound the target argument moved, said out loud rather than left to be discovered.

    It used to be two captures a loop, for free: the call took no arguments, so every one was
    byte-identical and ``RepeatSalience`` admitted two. Identity is name plus arguments, so each
    distinct target is now its own identity and the ceiling is **two per target, four a loop**.

    Four and not six is a property of the tool rather than of the policy: the third spelling a
    model can produce is the empty one, and that is refused before the body is called (see the
    no-target test above), so it costs a dispatch and takes no picture. Four and not unbounded is
    the exact match, since every accepted spelling would buy another two.
    """
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
    """The within-a-round clause is absolute, and it is what stops one round from spending the
    whole per-target allowance on the same picture twice before either result is read."""
    salience = RepeatSalience()
    first_round: list[list[ToolCall]] = [[]]

    assert salience.admits(_call("focus"), first_round) is True
    first_round[-1].append(_call("focus"))
    assert salience.admits(_call("focus"), first_round) is False
    assert salience.admits(_call("display"), first_round) is True


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
