"""Body domain values: the host state an OS action reads or writes."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from cortex_core.errors import BodyGatewayError
from cortex_core.images import ImagePart


class CaptureTarget(Enum):
    """What a capture is pointed at: the whole primary display, or one window."""

    DISPLAY = "display"
    FOCUS = "focus"


@dataclass(frozen=True, slots=True)
class VolumeState:
    """The host's audio output state: ``level`` in [0.0, 1.0] and whether it is ``muted``."""

    level: float
    muted: bool


@dataclass(frozen=True, slots=True)
class ScreenCapture:
    """One picture of the host's display, as the body returned it."""

    image: ImagePart
    source_width: int
    source_height: int
    captured_at: datetime
    target: CaptureTarget = CaptureTarget.DISPLAY

    @property
    def downscaled(self) -> bool:
        """Whether the picture is smaller than the display, so the tool can say so."""
        return (self.image.width, self.image.height) != (self.source_width, self.source_height)


def captured_at_from_unix_ms(unix_ms: int) -> datetime:
    """Read ``captured_at_unix_ms`` from the body as an aware UTC datetime.

    Zero, which the body sends when it has no clock reading, reads back as the epoch.
    """
    return datetime.fromtimestamp(unix_ms / 1000, tz=UTC)


def hold_to_the_bounds_asked_for(
    *, width: int, height: int, byte_count: int, max_edge: int, max_bytes: int
) -> None:
    """Raise when a capture exceeds the bounds this call asked the body for."""
    edge = max(width, height)
    if max_edge and edge > max_edge:
        msg = (
            f"body capture_screen answered {width}x{height}, over the {max_edge} px "
            "edge it was asked for"
        )
        raise BodyGatewayError(msg)
    if max_bytes and byte_count > max_bytes:
        msg = (
            f"body capture_screen answered {byte_count} bytes, over the {max_bytes} byte "
            "budget it was asked for"
        )
        raise BodyGatewayError(msg)
