"""InMemoryBodyGateway: the BodyGateway port held in memory (the gRPC adapter's twin).

Moved out of ``fakes.py`` (at its line-cap budget) when ADR-0025 grew the port with
``notify``; the ``cortex_core`` re-export is unchanged. Keeps the host's volume state in the
process; ``get_volume`` reports it, ``set_volume`` applies a change (clamping ``level`` to
[0.0, 1.0], the OS backend's own rule), and ``notify`` records the toast and answers the
scripted ``shown``. Setting ``shown=False`` scripts a body whose notifier declined (the reminder
then stays deliverable for the pull path). Constructed with ``fail`` set to a
``BodyGatewayError`` to script an unreachable body. For tests, CI, and experiments only.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from cortex_core.body import VolumeState
from cortex_core.errors import BodyGatewayError


@dataclass(frozen=True, slots=True)
class SentNotification:
    """One notify call the fake received, verbatim (for test assertions)."""

    title: str
    body: str
    reminder_id: str
    tainted: bool


class InMemoryBodyGateway:
    """BodyGateway held in memory as the contract twin of the gRPC adapter (ADR-0023/0025)."""

    def __init__(
        self,
        *,
        level: float = 0.5,
        muted: bool = False,
        shown: bool = True,
        fail: BodyGatewayError | None = None,
    ) -> None:
        self._level = level
        self._muted = muted
        self._shown = shown
        self._fail = fail
        self._notifications: list[SentNotification] = []

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

    @property
    def notifications(self) -> Sequence[SentNotification]:
        """The notify calls received so far, in order."""
        return tuple(self._notifications)
