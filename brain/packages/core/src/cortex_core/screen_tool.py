"""The ``capture_screen`` built-in: the cortex reads the user's screen (ADR-0029).

The cortex calls it like any tool. It runs through the audited ``ToolDispatcher`` and calls the
``BodyGateway`` port, which reaches the host body over ``BodyService``. Being an **internal**
built-in rather than an MCP tool makes it cortex-only by construction: a subagent never gets
one, which matters more here than for volume, since no subagent model on the mount carries a
vision projector and an image-bearing MCP result would arrive as an empty non-error string.

**A capture is always UNTRUSTED and always taints the turn.** A screen is a rendering of
arbitrary third-party content up to and including an attacker's browser tab, and the ``Trust``
docstring has named screen captures as untrusted since before any of this was built. The volume
built-ins stamp TRUSTED because host state is a float the OS authored; this is not that.
Tainting is not cosmetic: it closes every gated tool for the rest of the turn, refuses
autonomous task creation, and pins subagent spawns to the injection-robust model.

The boundary has to be that mechanical, because framing does not hold over pixels the way it
holds over text. Measured against a rendered-payload corpus (ADR-0029's 2026-08-04 image-arm
addendum), an instruction painted into the pixels is **not obeyed but described** for every
hijack-shaped attack, with and without the hardened preamble: overrides, task-completion spoofs,
system-prompt mimicry, roleplay, refusal suppression, payload splitting and both exfiltrations
all failed, and the outbound tool was never called from a picture. **Content manipulation is the
exception**, and it is the one the preamble was hardened for: told by a screen that every summary
must end with a given line, the cortex has ended its summary with that line, framed. No amount of
framing bounds a picture; a nonce can bracket text and cannot bracket pixels. So the tool marks
the turn through exactly the machinery every other untrusted result uses, with no special case,
and the existing denial does the rest.

Failure is deliberately asymmetric: every failure returns ``Trust.TRUSTED, is_error=True`` with
no images. Nothing untrusted arrived, so tainting on a dead body would gratuitously close the
user's gated tools for the rest of a turn in which nothing was read.

**Ungated by default**, with ``CORTEX_TOOLS_GATED=send_email,capture_screen`` as the documented
zero-code user opt-in (the ``set_volume`` precedent). The gate reason reads "this action is
outbound or irreversible", and a screen read is neither; and a gated call on a tainted turn is
hard-denied with the confirmer never consulted, so gating would make "read this email, then look
at my screen" structurally impossible and let a first capture self-deny a second.

**One input to that decision has moved and the decision has not.** The third leg used to be that
a confirm card could not describe what would be captured, the call taking no arguments. It takes
one now, so a card could say "the window you are looking at" or "your whole screen", which is a
promise worth something to a user. That is recorded rather than acted on: the other three legs
are untouched, and the maintainer is the one to overrule this, knowing the argument is now
weaker by a leg (ADR-0029's target addendum).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cortex_core.body import CaptureTarget, ScreenCapture
from cortex_core.body_failure import body_failure_message
from cortex_core.errors import BodyGatewayError
from cortex_core.ports import BodyGateway
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

CAPTURE_SCREEN_TOOL_NAME = "capture_screen"

# The infinitive the shared per-kind lead completes, so a refused capture says the body refused
# and only a capture that never reached the body says so.
_ACTION = "capture the screen"

# The vocabulary the model picks between, derived from the domain enum rather than restated, so
# a third target cannot reach the wire without reaching the schema. Declaration order, not
# alphabetical: it puts the whole display first, which is what this seam's zero means.
_TARGETS: tuple[CaptureTarget, ...] = tuple(CaptureTarget)
_TARGET_NAMES: tuple[str, ...] = tuple(target.value for target in _TARGETS)
_TARGET_BY_NAME: dict[str, CaptureTarget] = {target.value: target for target in _TARGETS}

# Written as instruction rather than as documentation, and worded off the measurement rather than
# off what the design expected of it (ADR-0029's window-crop addendum). The crop wins in exactly
# one place, 15 px text going from 5 of 12 to 9 or 10 of 12, it is level at every size above that,
# and over a whole desktop it reads worse than the shrunk screen because it cannot see anything
# outside the window. So the text steers the pick toward small text in one thing rather than
# toward the window in general, and it says out loud what a window costs. The detail claim is
# conditional because the mechanism is being unresampled rather than being cropped: a window wider
# than the capture edge is resampled exactly as the screen is and reads no better than it. Neither
# the model nor this tool can tell whether that happened, which is a deferral recorded in
# docs/refinements/index.md#vision rather than a field on the reply.
_DESCRIPTION = (
    "Take a picture of the user's screen and look at it. Use this when the user asks about what "
    "is on their screen, or refers to something you cannot see. The picture is attached to your "
    "view of the result. Always name a target. Use 'focus' for the window the user is looking "
    "at: it is cut out of the screen rather than shrunk down, so a window that is not oversized "
    "keeps its own detail and small text in it stays readable. That is the one thing it is "
    "better at, and it costs everything else: no other window, no taskbar, and nothing outside "
    "that window is in the picture, and a window too large to send whole is shrunk exactly as "
    "the screen is. Use 'display' for the whole screen: it is shrunk to fit, so fine print may "
    "be lost, and it is the only target that shows what else is open or where something is. So "
    "pick 'focus' when the answer turns on reading something small or exact in one thing in "
    "front of the user, such as an error, a figure, or a line of a document, and 'display' "
    "otherwise. If 'focus' comes back saying there is no window to capture, the user is looking "
    "at a bare desktop, so ask again with 'display'."
)

_TARGET_HELP = (
    "'focus' for the window the user is looking at (cut out of the screen, so small text in it "
    "stays readable unless the window is very large, and nothing outside it is captured), "
    "'display' for the whole screen (shrunk to fit, so fine print may be lost)."
)
_TARGET_REQUIRED = f"capture_screen requires 'target': {_TARGET_HELP}"
_BAD_TARGET = f"'target' must be one of: {', '.join(_TARGET_NAMES)}"


def _parse_target(arguments: Mapping[str, Any]) -> CaptureTarget | str:
    """Read the model's ``target``; return the domain value or an error message string.

    Never raises and never guesses. A missing target is refused rather than defaulted, on two
    grounds that point the same way. The default it would take is the **whole screen**, which is
    the more exposing of the two pictures, and choosing the wider one for a question the model has
    not said is about the screen as a whole is the wrong direction. (This used to claim the whole
    screen was the less legible picture too. The window-crop measurement narrows that to the
    smallest text on the screen: over a whole desktop the shrunk screen reads *more* of it, since
    a crop cannot see past its window. The exposure leg is untouched and carries the decision.)
    And every spelling this tool accepts is
    another two captures a loop can take, since repeat detection keys on the arguments as
    written: refusing an omitted or unrecognized target costs a dispatch and takes no picture,
    which is what keeps the bound at two per target rather than two per way of asking. For the
    same reason the match is exact: accepting ``Display`` beside ``display`` would add a whole
    identity that captures.
    """
    raw = arguments.get("target")
    if not isinstance(raw, str):
        return _TARGET_REQUIRED
    target = _TARGET_BY_NAME.get(raw)
    if target is None:
        return _BAD_TARGET
    return target


@dataclass(frozen=True, slots=True)
class CaptureBounds:
    """What the composition root asks the body for, when vision is available at all.

    A value rather than two loose ints so ``build_builtin_tools`` can say "vision, with these
    bounds" in one argument, and so "vision is off" is expressed by its absence rather than by
    a third flag that could disagree with the bounds beside it.
    """

    max_edge: int = 0
    max_bytes: int = 0


def describe(capture: ScreenCapture) -> str:
    """The brain-authored stand-in text that accompanies the picture.

    Integers and a timestamp only. It deliberately carries no window title and no application
    name: both are attacker-chosen strings, and a caption assembled from them would be the one
    part of an untrusted screen that arrives outside the picture. Naming the source size states
    the fact that the picture is a shrunk view, and that is all it does: measured against a 4K
    corpus with "unreadable" offered as an allowed answer, the cortex declined on 3 of 47
    illegible strings and invented the other 38, so this sentence does not buy a refusal
    (ADR-0029's legibility addendum). What moves that line is the image token budget, which is a
    deployment setting rather than a caption.

    **Two sentences, because the two pictures are two different things.** A window was *cropped*
    out of the display, not shrunk down from it, and one that fits the capture edge was not
    resampled at all, so the display sentence's "downscaled from WxH" clause would tell the model
    about a whole desktop it was never shown. The window sentence therefore names the display as
    what the picture was cut out of and says outright that the rest of the screen is missing,
    which is the one thing the model can act on: it can ask again for the display.

    It claims **nothing** about whether the window itself was then shrunk, because the reply does
    not say and this is not the place to guess. The crop's own size is region geometry, which
    this seam declines to carry in either direction, and the whole design point of the window
    target is that a window inside the capture edge crosses pixel for pixel. The window-crop
    measurement priced that silence rather than removing it: one of its five windows was wider
    than the capture edge, was resampled to exactly what the whole screen is resampled to, and
    read no better than it. Telling the two apart wants one bit on the reply, and it is recorded
    in docs/refinements/index.md#vision rather than built, on the ground that the sentence it would
    write is the sentence this ADR already measured the model not to act on.

    Which sentence is used is the body's answer (``capture.target``) rather than what was asked
    for, so a window filling the display reads as a display capture, exactly as the OS receipt
    the user sees does.
    """
    image = capture.image
    size = f"{image.width}x{image.height} {image.mime_type}"
    source = f"{capture.source_width}x{capture.source_height}"
    taken = f"taken at {capture.captured_at.isoformat()}."
    attached = (
        "The picture is attached to this message as an image part; it cannot be fenced as text."
    )
    if capture.target is CaptureTarget.FOCUS:
        return (
            f"screen capture of one window, cropped out of the {source} primary display: "
            f"{size}, {taken} The rest of the screen was not captured. {attached}"
        )
    scale = f", downscaled from {source}" if capture.downscaled else ""
    return f"screen capture of the primary display: {size}{scale}, {taken} {attached}"


class CaptureScreenTool:
    """Built-in ``capture_screen`` tool over a ``BodyGateway`` (ADR-0029)."""

    def __init__(self, body: BodyGateway, *, max_edge: int = 0, max_bytes: int = 0) -> None:
        self._body = body
        self._max_edge = max_edge
        self._max_bytes = max_bytes

    @property
    def spec(self) -> ToolSpec:
        """The one-argument, ungated spec advertised to the cortex.

        **What this costs, said out loud.** Captures used to be bounded per loop for free: the
        call took no arguments, so every one was byte-identical and ``RepeatSalience`` admitted
        two of them. Identity is name plus arguments, so a target makes each distinct spelling
        its own identity and the ceiling is now **two captures per target, four per loop**. It is
        four rather than six because a missing target is refused rather than defaulted, so the
        empty-arguments spelling costs a dispatch and takes no picture, and it is four rather
        than unbounded because the vocabulary is closed and matched exactly. Doubling the worst
        case is defensible on what the second target is: two pictures of one window and two of
        the screen is what a model that legitimately re-looks does, and each is still charged to
        the same dispatch pool and the same budget.
        """
        return ToolSpec(
            name=CAPTURE_SCREEN_TOOL_NAME,
            description=_DESCRIPTION,
            parameters={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "enum": list(_TARGET_NAMES),
                        "description": _TARGET_HELP,
                    }
                },
                "required": ["target"],
            },
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Capture the screen, or report why not.

        The bytes ride on the result that carries them, so the taint ledger observes the very
        value holding the pixels; there is no window in which the image is in context and the
        turn is not yet marked.

        A target the tool does not recognize is a **tool error** and never an exception: the
        model chose it, the model can correct it, and a raise here would kill the turn instead
        of the call. Nothing is captured on that path, so nothing taints.

        A failure is worded from its ``BodyFailure`` kind, so the shipping default (capture
        switched off, answered ``PERMISSION_DENIED`` at once) reads as a refusal rather than as
        an unreachable body.
        """
        target = _parse_target(call.arguments)
        if isinstance(target, str):
            return ToolResult(call_id=call.id, content=target, is_error=True, trust=Trust.TRUSTED)
        try:
            capture = await self._body.capture_screen(
                max_edge=self._max_edge, max_bytes=self._max_bytes, target=target
            )
        except BodyGatewayError as err:
            return ToolResult(
                call_id=call.id,
                content=body_failure_message(err, action=_ACTION),
                is_error=True,
                trust=Trust.TRUSTED,
            )
        return ToolResult(
            call_id=call.id,
            content=describe(capture),
            trust=Trust.UNTRUSTED,
            images=(capture.image,),
        )
