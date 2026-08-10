"""The ``capture_screen`` built-in: the cortex reads the user's screen (ADR-0029)."""

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

# Written as instruction rather than as documentation: its whole job is to make the model pick
# the window when the user is asking about one thing in front of them, which is the case the
# 4K legibility measurement said the token budget alone cannot rescue.
_DESCRIPTION = (
    "Take a picture of the user's screen and look at it. Use this when the user asks about what "
    "is on their screen, or refers to something you cannot see. The picture is attached to your "
    "view of the result. Always name a target. Use 'focus' for the window the user is looking "
    "at: it is cut out of the screen at full detail, so small text stays readable, and it is "
    "the right choice whenever the question is about one thing in front of them, such as a "
    "document, an error, a page, or a message. Use 'display' for the whole screen: it is shrunk "
    "to fit, so fine print may be lost, and it is the right choice only when the question is "
    "about the screen as a whole, such as what is open or where something is. If 'focus' comes "
    "back saying there is no window to capture, the user is looking at a bare desktop, so ask "
    "again with 'display'."
)

_TARGET_HELP = (
    "'focus' for the window the user is looking at (full detail, small text readable), "
    "'display' for the whole screen (shrunk to fit)."
)
_TARGET_REQUIRED = f"capture_screen requires 'target': {_TARGET_HELP}"
_BAD_TARGET = f"'target' must be one of: {', '.join(_TARGET_NAMES)}"


def _parse_target(arguments: Mapping[str, Any]) -> CaptureTarget | str:
    """Read the model's ``target``; return the domain value or an error message string."""
    raw = arguments.get("target")
    if not isinstance(raw, str):
        return _TARGET_REQUIRED
    target = _TARGET_BY_NAME.get(raw)
    if target is None:
        return _BAD_TARGET
    return target


@dataclass(frozen=True, slots=True)
class CaptureBounds:
    """What the composition root asks the body for, when vision is available at all."""

    max_edge: int = 0
    max_bytes: int = 0


def describe(capture: ScreenCapture) -> str:
    """The brain-authored stand-in text that accompanies the picture."""
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
        """The one-argument, ungated spec advertised to the cortex."""
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
        """Capture the screen, or report why not."""
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
