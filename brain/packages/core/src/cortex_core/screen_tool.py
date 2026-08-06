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
outbound or irreversible", and a screen read is neither; the confirm card could not describe
what will be captured, since the call takes no arguments; and a gated call on a tainted turn is
hard-denied with the confirmer never consulted, so gating would make "read this email, then look
at my screen" structurally impossible and let a first capture self-deny a second.
"""

from dataclasses import dataclass

from cortex_core.body import ScreenCapture
from cortex_core.errors import BodyGatewayError
from cortex_core.ports import BodyGateway
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

CAPTURE_SCREEN_TOOL_NAME = "capture_screen"

_UNREACHABLE = "could not reach the body to capture the screen"

_DESCRIPTION = (
    "Take a picture of the user's primary display and look at it. Use this when the user asks "
    "about what is on their screen, or refers to something you cannot see. The picture is "
    "attached to your view of the result. It takes no arguments and captures the whole display."
)


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
    """
    image = capture.image
    scale = (
        f", downscaled from {capture.source_width}x{capture.source_height}"
        if capture.downscaled
        else ""
    )
    return (
        f"screen capture of the primary display: {image.width}x{image.height} "
        f"{image.mime_type}{scale}, taken at {capture.captured_at.isoformat()}. "
        "The picture is attached to this message as an image part; it cannot be fenced as text."
    )


class CaptureScreenTool:
    """Built-in ``capture_screen`` tool over a ``BodyGateway`` (ADR-0029)."""

    def __init__(self, body: BodyGateway, *, max_edge: int = 0, max_bytes: int = 0) -> None:
        self._body = body
        self._max_edge = max_edge
        self._max_bytes = max_bytes

    @property
    def spec(self) -> ToolSpec:
        """The no-argument, ungated spec advertised to the cortex.

        No arguments at all, which is also what bounds captures per turn for free: repeat
        detection keys on name plus arguments, so every call is byte-identical and the existing
        identical-dispatch cap applies without a new counter.
        """
        return ToolSpec(
            name=CAPTURE_SCREEN_TOOL_NAME,
            description=_DESCRIPTION,
            parameters={"type": "object", "properties": {}},
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Capture the screen, or report why not.

        The bytes ride on the result that carries them, so the taint ledger observes the very
        value holding the pixels; there is no window in which the image is in context and the
        turn is not yet marked.
        """
        try:
            capture = await self._body.capture_screen(
                max_edge=self._max_edge, max_bytes=self._max_bytes
            )
        except BodyGatewayError as err:
            return ToolResult(
                call_id=call.id,
                content=f"{_UNREACHABLE}: {err}",
                is_error=True,
                trust=Trust.TRUSTED,
            )
        return ToolResult(
            call_id=call.id,
            content=describe(capture),
            trust=Trust.UNTRUSTED,
            images=(capture.image,),
        )
