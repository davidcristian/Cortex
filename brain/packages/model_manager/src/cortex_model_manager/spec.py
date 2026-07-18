"""What one hosted model's process is, and the roster of logical ids one daemon serves.

Pure values, no I/O, shared by the supervisor, the control API, and the config that builds them.
A logical model id (ADR-0004 decision 2) is the only name that ever crosses the control API; the
artifact path, the port, ``-ngl`` and the context flags live here and nowhere else, which is what
lets a deployment re-point a tier without the brain knowing (ADR-0030 decision 3).

The roster is fixed at boot from the daemon's own env. Nothing a request carries can add a model,
change an argv, or name a path: the client of this API is the brain, which streams model output
and dispatches tools, so a request-supplied argv would be remote code execution against the GPU
container (ADR-0030 decision 3's rejected alternatives are all about that blast radius).
"""

from collections.abc import Iterable
from dataclasses import dataclass

_MIN_PORT = 1
_MAX_PORT = 65535


class RosterError(ValueError):
    """A roster could not be built: a boot-time misconfiguration, never a runtime surprise."""


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """One logical model the supervisor can run: its id, its port, and its whole argv.

    ``argv`` is complete and already includes the binary, so the supervisor spawns it verbatim
    and holds no opinion about llama.cpp's flags. ``port`` is fixed per model (ADR-0030
    decision 3: cortex 8080, deep model 8081, GPU subagent 8083) so the brain's endpoint map is
    static config rather than something discovered at runtime.
    """

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
        """Where this model's own server answers readiness: loopback, since it is a sibling.

        The child binds ``0.0.0.0`` so the brain container can reach it by service name, but the
        supervisor probes it over loopback inside its own container, which needs no name
        resolution and cannot be answered by anything outside.
        """
        return f"http://127.0.0.1:{self.port}/health"


def build_roster(specs: Iterable[ModelSpec]) -> dict[str, ModelSpec]:
    """Index specs by logical id, refusing a duplicate id or two models sharing a port.

    A shared port is the misconfiguration that would quietly defeat a swap: the second child
    dies at once with ``couldn't bind HTTP server socket`` while the first keeps answering
    ``/health`` on that port, so a status that trusted the probe alone would call the dead model
    ready and leave the previous weights resident. The supervisor closes that hole at runtime by
    reading its own child's exit before it probes anything; this closes it at boot, where the
    operator can still fix it.
    """
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
