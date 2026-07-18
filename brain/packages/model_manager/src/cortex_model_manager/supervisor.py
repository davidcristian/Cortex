"""One ``llama-server`` child per logical model: start, stop, and say what is true (ADR-0030 d3).

The whole behaviour behind the ``ModelHost`` port's three verbs, over the ``ChildProcesses`` and
``HealthProbe`` seams so all of it is gated without spawning anything. The port's promises are
kept here, and each one costs a specific rule:

- **Both verbs are idempotent**, because a swap re-issues either without checking first
  (``residency_moves.py``): starting a running model is a no-op, stopping an absent one is a
  no-op, and a start whose spawn fails leaves nothing behind.
- **``start`` returns long before the model is ready.** A start is a spawn and nothing more, so
  the swap's health gate is the only thing that ever decides readiness. Blocking here would put a
  minutes-long load at the mercy of an HTTP client's timeout instead of the plan's bound.
- **``stop`` does not return until the child is dead and reaped**, so its VRAM is genuinely gone
  before the caller starts the next model. ``swap_in`` stops the cortex and starts the deep model
  with nothing in between, so a still-dying cortex holding ~11 GB would CUDA-OOM the load.
- **``status`` reads the process before it trusts the probe.** Measured: a child that failed to
  bind dies in ~0.24 s with exit code 1 while the *previous* model keeps answering 200 on that
  port, so a status that proxied ``/health`` alone would report the dead model READY and leave
  the old weights resident, silently defeating the swap. The exit code wins over the probe.
- **One lock per logical model** serializes its three verbs, because a stop racing a start is the
  race that produces the bind failure above.
"""

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass

from cortex_core import ModelHostState
from cortex_model_manager.children import ChildProcess, ChildProcesses
from cortex_model_manager.probe import HealthProbe
from cortex_model_manager.spec import ModelSpec

# How long a child gets to exit on SIGTERM before it is killed. Measured on the dev GPU with a
# small model resident: llama-server exits 0 in 0.14 s to 0.38 s, so seconds are generous; a
# tier-scale model is the user's to re-measure (docs/runbooks/model-swap.md).
DEFAULT_STOP_GRACE_S = 10.0

# How long a SIGKILLed child gets to be reaped before the stop is reported as failed. A killed
# process only lingers in uninterruptible I/O, which on the model mount is possible, so this is a
# bound rather than an unbounded wait: the swap must be told rather than hang.
DEFAULT_REAP_TIMEOUT_S = 30.0

_logger = logging.getLogger(__name__)


class SupervisorError(RuntimeError):
    """A model process could not be started or stopped. Crosses the wire as a 503."""


class UnknownModelError(SupervisorError):
    """No such logical model in this daemon's roster. Crosses the wire as a 404."""


@dataclass(frozen=True, slots=True)
class ModelStatus:
    """What one logical model is doing, plus the human half the control API returns.

    ``state`` is the port's own enum, so the two sides of the wire cannot drift about what the
    four words mean. ``detail`` is for the log and the runbook: it carries the exit code of a
    process that died, the port a ready model serves on, and the pid of one still loading.
    """

    model: str
    state: ModelHostState
    detail: str


class ModelSupervisor:
    """Runs at most one child per logical model, and reports honestly on each."""

    def __init__(
        self,
        roster: Mapping[str, ModelSpec],
        processes: ChildProcesses,
        probe: HealthProbe,
        *,
        stop_grace_s: float = DEFAULT_STOP_GRACE_S,
        reap_timeout_s: float = DEFAULT_REAP_TIMEOUT_S,
    ) -> None:
        self._roster = dict(roster)
        self._processes = processes
        self._probe = probe
        self._stop_grace_s = stop_grace_s
        self._reap_timeout_s = reap_timeout_s
        # A model is present here from the moment it is spawned until a stop has reaped it. A
        # present child with an exit code died unasked, which is the difference between FAILED
        # and STOPPED; the roster's own keys are the only ids that ever reach this dict.
        self._children: dict[str, ChildProcess] = {}
        self._locks = {model: asyncio.Lock() for model in self._roster}

    @property
    def models(self) -> tuple[str, ...]:
        """The logical ids this daemon serves, in roster order. Nothing can add to them."""
        return tuple(self._roster)

    async def start(self, model: str) -> None:
        """Begin loading ``model``; return as soon as the process exists, ready or not."""
        spec = self._spec(model)
        async with self._locks[model]:
            running = self._children.get(model)
            if running is not None and running.returncode is None:
                return
            # A child that died on its own is replaced rather than kept, so a FAILED tier can be
            # restarted: boot recovery and the swap back both start a model that may have failed.
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
                # Deliberately before the delete: a child that will not die is still ours and
                # still holds VRAM, so it must keep being reported rather than vanish into
                # STOPPED. The caller's retry then tries again on the same process.
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
                _logger.exception("a model process could not be stopped at shutdown")

    def _spec(self, model: str) -> ModelSpec:
        """The roster entry, or the typed refusal every verb shares."""
        spec = self._roster.get(model)
        if spec is None:
            msg = f"unknown model {model!r}; this host serves {', '.join(self._roster) or 'none'}"
            raise UnknownModelError(msg)
        return spec

    async def _end(self, model: str, child: ChildProcess) -> None:
        """SIGTERM, then SIGKILL after the grace, and wait out the reaping either way."""
        child.terminate()
        if await self._reaped(child, self._stop_grace_s):
            return
        _logger.warning(
            "a model process ignored SIGTERM; killing it",
            extra={"model": model, "pid": child.pid, "grace_s": self._stop_grace_s},
        )
        child.kill()
        if await self._reaped(child, self._reap_timeout_s):
            return
        msg = (
            f"model {model!r} (pid {child.pid}) survived SIGKILL for {self._reap_timeout_s}s; "
            "its GPU memory is still held, so nothing else can be loaded"
        )
        _logger.error(msg, extra={"model": model, "pid": child.pid})
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
