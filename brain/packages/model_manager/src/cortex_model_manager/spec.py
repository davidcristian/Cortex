"""What one hosted model's process is, and the roster of logical ids one daemon serves."""

from collections.abc import Iterable
from dataclasses import dataclass

_MIN_PORT = 1
_MAX_PORT = 65535


class RosterError(ValueError):
    """A roster could not be built: a boot-time misconfiguration, never a runtime surprise."""


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """One logical model the supervisor can run: its id, its port, and its whole argv."""

    model: str
    port: int
    argv: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.model:
            msg = "ModelSpec.model must be a non-empty logical id"
            raise RosterError(msg)
        if not _MIN_PORT <= self.port <= _MAX_PORT:
            msg = f"ModelSpec.port for {self.model!r} must be in 1..65535, got {self.port}"
            raise RosterError(msg)
        if not self.argv:
            msg = f"ModelSpec.argv for {self.model!r} must name a binary to run"
            raise RosterError(msg)

    @property
    def health_url(self) -> str:
        """Where this model's own server answers readiness: loopback, since it is a sibling."""
        return f"http://127.0.0.1:{self.port}/health"


def build_roster(specs: Iterable[ModelSpec]) -> dict[str, ModelSpec]:
    """Index specs by logical id, refusing a duplicate id or two models sharing a port."""
    roster: dict[str, ModelSpec] = {}
    ports: dict[int, str] = {}
    for spec in specs:
        if spec.model in roster:
            msg = f"duplicate logical model id in the roster: {spec.model!r}"
            raise RosterError(msg)
        if (user := ports.get(spec.port)) is not None:
            msg = (
                f"models {user!r} and {spec.model!r} share port {spec.port}; one would fail to "
                "bind while the other kept answering /health on it"
            )
            raise RosterError(msg)
        roster[spec.model] = spec
        ports[spec.port] = spec.model
    return roster
