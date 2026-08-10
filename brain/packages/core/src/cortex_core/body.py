"""Body domain values: the host state an OS action reads or writes (ADR-0023).

Pure data, no I/O and no ``ports`` import. That lets ``ports.py`` depend on these without a
cycle, exactly as ``tools.py`` is depended on. A ``VolumeState`` is the core's mirror of the
seam's ``VolumeState`` wire message; the adapter (``cortex_body_client``) translates between
them so no wire type ever enters the core.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from cortex_core.images import ImagePart


class CaptureTarget(Enum):
    """What a capture is pointed at: the whole primary display, or one window (ADR-0029).

    The domain mirror of the seam's ``CaptureTarget`` and of the body's Rust enum of the same
    name, so no wire type reaches the core. A **closed vocabulary the body resolves**, never a
    rectangle the caller names: only the host knows where windows are, and the ADR's own
    measurement says a model asked to name one would name a wrong one rather than decline.

    The member *values* are the strings the model picks between in the ``capture_screen``
    schema, so the vocabulary is spelled exactly once on this side of the seam. Deriving the
    schema from the enum rather than restating it is what keeps a third target from reaching the
    wire without reaching the model, and it is the only half of that coupling a gate can hold;
    the other half, these members against the proto's, is generated on both sides and is
    recorded in ``docs/refinements/repo-gates.md``.

    ``DISPLAY`` is the wire's zero and the behaviour every capture had before the target existed,
    which is what makes it the honest reading of a reply from a body that sets no target at all.
    """

    DISPLAY = "display"
    FOCUS = "focus"


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
    downscale. ``source_width``/``source_height`` are the display's own size before it **on both
    paths**: they say how big the screen is, never how big the crop was, so a window capture
    still reports the display it was cut out of.

    ``target`` is what the body says the picture actually *is*, which is the only thing that
    tells those two paths apart, since the blob looks the same either way. The body reads it off
    what it encoded rather than off what was asked for, so a window filling the display answers
    ``DISPLAY``, and the receipt the user sees is picked by the same predicate. It defaults to
    ``DISPLAY`` because that is the wire's zero: a body that sets no target can only take a
    whole-display picture, so the default is a reading rather than a guess.

    The name deliberately matches the body's Rust ``ScreenCapture`` trait. They are the two
    ends of one capability: the trait is what a host implements, this is what the brain
    receives.
    """

    image: ImagePart
    source_width: int
    source_height: int
    captured_at: datetime
    target: CaptureTarget = CaptureTarget.DISPLAY

    @property
    def downscaled(self) -> bool:
        """Whether the picture is smaller than the **display**, so the tool can say so.

        Only meaningful for a ``DISPLAY`` capture. A window is cut out of the display before it
        is shrunk, so for ``FOCUS`` this compares a crop against a screen and answers about
        neither; ``describe`` reads ``target`` first and never asks.
        """
        return (self.image.width, self.image.height) != (self.source_width, self.source_height)


def captured_at_from_unix_ms(unix_ms: int) -> datetime:
    """Read the seam's ``captured_at_unix_ms`` as an aware UTC datetime.

    Zero means the body had no honest clock reading and said so rather than inventing one; it
    reads back as the epoch, which is visibly not a capture time.
    """
    return datetime.fromtimestamp(unix_ms / 1000, tz=UTC)
