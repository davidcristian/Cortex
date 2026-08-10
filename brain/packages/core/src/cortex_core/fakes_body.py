"""InMemoryBodyGateway: the BodyGateway port held in memory (the gRPC adapter's twin).

Moved out of ``fakes.py`` (at its line-cap budget) when ADR-0025 grew the port with
``notify``; the ``cortex_core`` re-export is unchanged. Keeps the host's volume state in the
process; ``get_volume`` reports it, ``set_volume`` applies a change (clamping ``level`` to
[0.0, 1.0], the OS backend's own rule), and ``notify`` records the toast and answers the
scripted ``shown``. Setting ``shown=False`` scripts a body whose notifier declined (the reminder
then stays deliverable for the pull path). Constructed with ``fail`` set to a
``BodyGatewayError`` to script an unreachable body. ``capture_screen`` (ADR-0029) answers the
scripted ``capture`` and records what was asked for, so a test can assert the hints the caller
sent without a wire. For tests, CI, and experiments only.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from cortex_core.body import CaptureTarget, ScreenCapture, VolumeState
from cortex_core.errors import BodyGatewayError
from cortex_core.images import ImagePart


@dataclass(frozen=True, slots=True)
class SentNotification:
    """One notify call the fake received, verbatim (for test assertions)."""

    title: str
    body: str
    reminder_id: str
    tainted: bool


@dataclass(frozen=True, slots=True)
class CaptureAsk:
    """One capture_screen call the fake received, verbatim (for test assertions)."""

    max_edge: int
    max_bytes: int
    target: CaptureTarget


# A one-pixel PNG, the smallest thing that satisfies ``ImagePart`` without a fixture file.
_PIXEL_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080200000090"
    "7753de0000000c4944415408d763f8cfc00000030101002d0d0aa4000000"
    "0049454e44ae426082"
)


def default_capture() -> ScreenCapture:
    """The capture the fake answers unless a test scripts another one."""
    return ScreenCapture(
        image=ImagePart(data=_PIXEL_PNG, mime_type="image/png", width=1, height=1),
        source_width=2,
        source_height=2,
        captured_at=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
    )


class InMemoryBodyGateway:
    """BodyGateway held in memory as the contract twin of the gRPC adapter (ADR-0023/0025/0029)."""

    def __init__(
        self,
        *,
        level: float = 0.5,
        muted: bool = False,
        shown: bool = True,
        capture: ScreenCapture | None = None,
        fail: BodyGatewayError | None = None,
    ) -> None:
        self._level = level
        self._muted = muted
        self._shown = shown
        self._capture = capture if capture is not None else default_capture()
        self._fail = fail
        self._notifications: list[SentNotification] = []
        self._captures: list[CaptureAsk] = []

    async def get_volume(self) -> VolumeState:
        """Report the current volume state, or raise the scripted failure."""
        if self._fail is not None:
            raise self._fail
        return VolumeState(level=self._level, muted=self._muted)

    async def set_volume(
        self, *, level: float | None = None, mute: bool | None = None
    ) -> VolumeState:
        """Apply a change (clamping ``level``) and report the result, or raise the failure."""
        if self._fail is not None:
            raise self._fail
        if level is not None:
            self._level = min(1.0, max(0.0, level))
        if mute is not None:
            self._muted = mute
        return VolumeState(level=self._level, muted=self._muted)

    async def notify(
        self, *, title: str, body: str, reminder_id: str, tainted: bool = False
    ) -> bool:
        """Record the toast and answer the scripted ``shown``, or raise the failure."""
        if self._fail is not None:
            raise self._fail
        self._notifications.append(
            SentNotification(title=title, body=body, reminder_id=reminder_id, tainted=tainted)
        )
        return self._shown

    async def capture_screen(
        self,
        *,
        max_edge: int = 0,
        max_bytes: int = 0,
        target: CaptureTarget = CaptureTarget.DISPLAY,
    ) -> ScreenCapture:
        """Record what was asked for and answer the scripted capture, or raise the failure.

        The scripted capture is answered **verbatim**, target included, rather than being
        rewritten to match the ask. That is the real body's behaviour: what a reply says it
        points at is read off the picture that was encoded, so a focus request can honestly come
        back as a display capture (a window filling the screen), and a test that wants the
        window sentence scripts a window capture.
        """
        if self._fail is not None:
            raise self._fail
        self._captures.append(CaptureAsk(max_edge=max_edge, max_bytes=max_bytes, target=target))
        return self._capture

    @property
    def notifications(self) -> Sequence[SentNotification]:
        """The notify calls received so far, in order."""
        return tuple(self._notifications)

    @property
    def captures(self) -> Sequence[CaptureAsk]:
        """The capture_screen calls received so far, in order."""
        return tuple(self._captures)
