"""The brain→body port (typing.Protocol): what the brain may ask the host body to do (ADR-0023).

Split out of ``ports.py`` for the line cap (the ``ports_stores.py`` precedent) and re-exported
there, so every existing ``from cortex_core.ports import BodyGateway`` keeps resolving. It sits
alone because it is the seam's other direction rather than a store or a model process: every
method here crosses to the host over ``BodyService``, and the set grows once per host capability
the brain learns to reach. Method bodies are one-line ``...`` stubs; failures cross this boundary
exclusively as the typed ``BodyGatewayError`` in ``errors.py``.
"""

from typing import Protocol

from cortex_core.body import ScreenCapture, VolumeState


class BodyGateway(Protocol):
    """Calls the host body to read or change an OS setting over the brain→body seam (ADR-0023).

    The first bidirectional direction of the seam: the brain is the client of the body's
    ``BodyService``. ``get_volume`` reports the host's current audio state; ``set_volume``
    applies a change (``level`` clamped to [0.0, 1.0], ``mute``, or both, with a ``None`` field
    left untouched) and reports the state after. Both return a domain ``VolumeState``; no wire
    type crosses this boundary. ``notify`` (ADR-0025) shows a native notification (the push
    half of reminder delivery), returning whether the body displayed it (``False`` or an error
    leaves the reminder deliverable for the pull path; ``tainted`` marks attacker-influenced
    text so the body can badge it and must render it inert). ``capture_screen`` (ADR-0029)
    reads the host's primary display and returns a domain ``ScreenCapture``; ``max_edge`` and
    ``max_bytes`` are hints the body clamps and may ignore, so the caller re-verifies the reply
    it gets. Failures (the body unreachable,
    an OS error, an unimplemented capability) surface as ``BodyGatewayError``, which callers
    turn into recoverable outcomes. The port is deliberately abstract so the connectivity
    fallback (a body-initiated tunnel, ADR-0001 Q3) is a later adapter, not a seam change.

    **A capture is attempted exactly once and never retried.** This is a decision, not an
    omission. A repeat would photograph a *different* screen, possibly after the user switched
    windows, so it neither reproduces the answer nor leaves the world unchanged, and it would
    fire a second host receipt for one user intent. Nothing in the brain retries a body call
    today, so the correct posture already holds; it is written down here so a future retry
    decorator has to exclude this method deliberately.
    """

    async def get_volume(self) -> VolumeState: ...

    async def set_volume(
        self, *, level: float | None = None, mute: bool | None = None
    ) -> VolumeState: ...

    async def notify(
        self, *, title: str, body: str, reminder_id: str, tainted: bool = False
    ) -> bool: ...

    async def capture_screen(self, *, max_edge: int = 0, max_bytes: int = 0) -> ScreenCapture: ...
