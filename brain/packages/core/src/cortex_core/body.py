"""Body domain values: the host state an OS action reads or writes (ADR-0023).

Pure data, no I/O and no ``ports`` import. That lets ``ports.py`` depend on these without a
cycle, exactly as ``tools.py`` is depended on. A ``VolumeState`` is the core's mirror of the
seam's ``VolumeState`` wire message; the adapter (``cortex_body_client``) translates between
them so no wire type ever enters the core.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VolumeState:
    """The host's audio output state: ``level`` in [0.0, 1.0] and whether it is ``muted``.

    Returned by every ``BodyGateway`` volume call. A read reports the current state, a write
    reports the state *after* applying the change, so the cortex always sees ground truth.
    """

    level: float
    muted: bool
