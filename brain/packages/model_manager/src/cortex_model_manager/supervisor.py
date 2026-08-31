"""One ``llama-server`` child per logical model: start it, stop it, and report its state."""

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import uuid4

from cortex_core import ControlBounds, ModelHostState
from cortex_model_manager.children import ChildProcess, ChildProcesses
from cortex_model_manager.probe import HealthProbe
from cortex_model_manager.spec import ModelSpec

# Measured on the dev GPU: an idle llama-server exits on SIGTERM in 0.14 s to 0.40 s, while one
# with a request in flight ignores SIGTERM entirely and is killed, costing the whole grace
# (10.09 s and 10.90 s end to end). Shortening it would SIGKILL a model mid answer.
DEFAULT_STOP_GRACE_S = 10.0

# A killed process only lingers in uninterruptible I/O, which the model mount can produce, so
# the wait is bounded: a swap must be told rather than hang.
DEFAULT_REAP_TIMEOUT_S = 30.0

# The readiness probe's own client deadline. It is still one of this daemon's three bounds,
# because `status` probes inside the same per-model lock a `stop` takes: measured, a status
# against a SIGSTOPped child took 5.80 s and the stop queued behind it 15.70 s.
DEFAULT_PROBE_TIMEOUT_S = 5.0

_logger = logging.getLogger(__name__)


class SupervisorError(RuntimeError):
    """A model process could not be started or stopped."""


class UnknownModelError(SupervisorError):
    """No such logical model in this daemon's roster."""


@dataclass(frozen=True, slots=True)
class ModelStatus:
    """What one logical model is doing, plus the human half the control API returns."""

    model: str
    state: ModelHostState
    detail: str


class ModelSupervisor:
    """Runs at most one child per logical model, and reports the state of each."""

    def __init__(
        self,
        roster: Mapping[str, ModelSpec],
        processes: ChildProcesses,
        probe: HealthProbe,
        *,
        stop_grace_s: float = DEFAULT_STOP_GRACE_S,
        reap_timeout_s: float = DEFAULT_REAP_TIMEOUT_S,
        probe_timeout_s: float = DEFAULT_PROBE_TIMEOUT_S,
    ) -> None:
        self._roster = dict(roster)
        self._processes = processes
        self._probe = probe
        self._bounds = ControlBounds(
            probe_timeout_s=probe_timeout_s,
            stop_grace_s=stop_grace_s,
            reap_timeout_s=reap_timeout_s,
        )
        # Random rather than counted: a counter in a process that restarted begins again at
        # exactly the number a reader compares against to detect the restart.
        self._boot_id = uuid4().hex
        self._children: dict[str, ChildProcess] = {}
        self._locks = {model: asyncio.Lock() for model in self._roster}

    @property
    def models(self) -> tuple[str, ...]:
        """The logical ids this daemon serves, in roster order."""
        return tuple(self._roster)

    @property
    def control_bounds(self) -> ControlBounds:
        """The three bounds this daemon was wired with, as ``GET /health`` reports them."""
        return self._bounds

    @property
    def boot_id(self) -> str:
        """Which daemon this is, as ``GET /health`` names it, for the life of this process."""
        return self._boot_id

    async def start(self, model: str) -> None:
        """Begin loading ``model``; return as soon as the process exists, ready or not."""
        spec = self._spec(model)
        async with self._locks[model]:
            running = self._children.get(model)
            if running is not None and running.returncode is None:
                return
            try:
                child = await self._processes.spawn(spec.argv)
            except OSError as err:
                msg = f"could not start {model!r}: {err}"
                raise SupervisorError(msg) from err
            self._children[model] = child
            _logger.info(
                "started a model process",
                extra={"model": model, "pid": child.pid, "port": spec.port},
            )

    async def stop(self, model: str) -> None:
        """End ``model``'s process and do not return until it is reaped and its VRAM is free."""
        self._spec(model)
        async with self._locks[model]:
            child = self._children.get(model)
            if child is None:
                return
            if child.returncode is None:
                # Before the delete: a child that has not exited still holds VRAM, so it must
                # keep being reported rather than recorded as STOPPED.
                await self._end(model, child)
            del self._children[model]
            _logger.info("stopped a model process", extra={"model": model, "pid": child.pid})

    async def status(self, model: str) -> ModelStatus:
        """What ``model`` is doing: the process first, the health probe only if it is alive."""
        spec = self._spec(model)
        async with self._locks[model]:
            child = self._children.get(model)
            if child is None:
                return ModelStatus(model, ModelHostState.STOPPED, "no process is running")
            code = child.returncode
            if code is not None:
                return ModelStatus(
                    model, ModelHostState.FAILED, f"the process exited with code {code}"
                )
            if await self._probe.serving(spec.health_url):
                return ModelStatus(model, ModelHostState.READY, f"serving on port {spec.port}")
            return ModelStatus(model, ModelHostState.LOADING, f"pid {child.pid} is not serving yet")

    async def stop_all(self) -> None:
        """Stop every model, best effort: a shutdown that raises would leave the rest running."""
        for model in self._roster:
            try:
                await self.stop(model)
            except SupervisorError:
                _logger.exception(
                    "a model process could not be stopped at shutdown", extra={"model": model}
                )

    def _spec(self, model: str) -> ModelSpec:
        """The roster entry, or the typed error every verb raises for an id not in the roster."""
        spec = self._roster.get(model)
        if spec is None:
            msg = f"unknown model {model!r}; this host serves {', '.join(self._roster) or 'none'}"
            raise UnknownModelError(msg)
        return spec

    async def _end(self, model: str, child: ChildProcess) -> None:
        """SIGTERM, then SIGKILL after the grace, and wait out the reaping either way."""
        child.terminate()
        if await self._reaped(child, self._bounds.stop_grace_s):
            return
        _logger.warning(
            "a model process ignored SIGTERM; killing it",
            extra={"model": model, "pid": child.pid, "grace_s": self._bounds.stop_grace_s},
        )
        child.kill()
        if await self._reaped(child, self._bounds.reap_timeout_s):
            return
        # Raised and not also logged: both callers of `stop` log what they catch, so a line here
        # would print the same event and the same numbers twice.
        msg = (
            f"model {model!r} (pid {child.pid}) survived SIGKILL for "
            f"{self._bounds.reap_timeout_s}s; "
            "its GPU memory is still held, so nothing else can be loaded"
        )
        raise SupervisorError(msg)

    @staticmethod
    async def _reaped(child: ChildProcess, bound: float) -> bool:
        """Whether the child exited within ``bound`` seconds, awaiting its exit to reap it."""
        try:
            async with asyncio.timeout(bound):
                await child.wait()
        except TimeoutError:
            return False
        return True
