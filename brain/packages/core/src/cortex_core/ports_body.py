"""The brain→body port (typing.Protocol): what the brain may ask the host body to do (ADR-0023)."""

from typing import Protocol

from cortex_core.body import ScreenCapture, VolumeState


class BodyGateway(Protocol):
    """Calls the host body to read or change an OS setting over the brain→body seam (ADR-0023)."""

    async def get_volume(self) -> VolumeState: ...

    async def set_volume(
        self, *, level: float | None = None, mute: bool | None = None
    ) -> VolumeState: ...

    async def notify(
        self, *, title: str, body: str, reminder_id: str, tainted: bool = False
    ) -> bool: ...

    async def capture_screen(self, *, max_edge: int = 0, max_bytes: int = 0) -> ScreenCapture: ...
