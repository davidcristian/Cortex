"""Body domain values: the host state an OS action reads or writes (ADR-0023)."""

from dataclasses import dataclass
from datetime import UTC, datetime

from cortex_core.images import ImagePart


@dataclass(frozen=True, slots=True)
class VolumeState:
    """The host's audio output state: ``level`` in [0.0, 1.0] and whether it is ``muted``.

    Returned by every ``BodyGateway`` volume call. A read reports the current state, a write
    reports the state *after* applying the change, so the cortex always sees ground truth.
    """

    level: float
    muted: bool


@dataclass(frozen=True, slots=True)
class ScreenCapture:
    """One picture of the host's primary display, as the body handed it over (ADR-0029)."""

    image: ImagePart
    source_width: int
    source_height: int
    captured_at: datetime

    @property
    def downscaled(self) -> bool:
        """Whether the body shrank the display to fit, so the tool can say so."""
        return (self.image.width, self.image.height) != (self.source_width, self.source_height)


def captured_at_from_unix_ms(unix_ms: int) -> datetime:
    """Read the seam's ``captured_at_unix_ms`` as an aware UTC datetime.

    Zero means the body had no honest clock reading and said so rather than inventing one; it
    reads back as the epoch, which is visibly not a capture time.
    """
    return datetime.fromtimestamp(unix_ms / 1000, tz=UTC)
