"""Body domain values: the host state an OS action reads or writes (ADR-0023).

Pure data, no I/O and no ``ports`` import. That lets ``ports.py`` depend on these without a
cycle, exactly as ``tools.py`` is depended on. A ``VolumeState`` is the core's mirror of the
seam's ``VolumeState`` wire message; the adapter (``cortex_body_client``) translates between
them so no wire type ever enters the core.
"""

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
    """One picture of the host's primary display, as the body handed it over (ADR-0029).

    The domain mirror of the seam's ``ImageBlob``; the adapter translates, so no wire type
    enters the core. ``image`` is already validated and inside the byte budget (an
    ``ImagePart`` cannot exist otherwise), and it carries the size *after* the body's
    downscale. ``source_width``/``source_height`` are the display's own size before it, which
    is what lets the tool tell the model it is looking at a shrunk view instead of leaving it
    to guess why small text is unreadable.

    The name deliberately matches the body's Rust ``ScreenCapture`` trait. They are the two
    ends of one capability: the trait is what a host implements, this is what the brain
    receives.
    """

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
