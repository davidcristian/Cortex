"""The ``capture_screen`` built-in: the cortex reads the user's screen (ADR-0029)."""

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
    """What the composition root asks the body for, when vision is available at all."""

    max_edge: int = 0
    max_bytes: int = 0


def describe(capture: ScreenCapture) -> str:
    """The brain-authored stand-in text that accompanies the picture."""
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
        """The no-argument, ungated spec advertised to the cortex."""
        return ToolSpec(
            name=CAPTURE_SCREEN_TOOL_NAME,
            description=_DESCRIPTION,
            parameters={"type": "object", "properties": {}},
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Capture the screen, or report why not."""
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
