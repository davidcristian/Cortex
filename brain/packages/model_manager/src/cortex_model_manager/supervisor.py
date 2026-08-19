"""One ``llama-server`` child per logical model: start, stop, and say what is true (ADR-0030 d3).

The whole behaviour behind the ``ModelHost`` port's three verbs, over the ``ChildProcesses`` and
``HealthProbe`` seams so all of it is gated without spawning anything. The port's promises are
kept here, and each one costs a specific rule:

- **Both verbs are idempotent**, because a swap re-issues either without checking first
  (``residency_moves.py``): starting a running model is a no-op, stopping an absent one is a
  no-op, and a start whose spawn fails adds nothing. A failed spawn also **removes** nothing: a
  tier whose previous child had died goes on reporting that child's exit code rather than being
  erased by the replacement that could not be started, since the spawn's own failure is what the
  ``start`` raises and the exit code is what the runbook reads.
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
from uuid import uuid4

from cortex_core import ControlBounds, ModelHostState
from cortex_model_manager.children import ChildProcess, ChildProcesses
from cortex_model_manager.probe import HealthProbe
from cortex_model_manager.spec import ModelSpec

# How long a child gets to exit on SIGTERM before it is killed. Measured on the dev GPU, and the
# two cases are nothing like each other: an **idle** llama-server exits 0 in 0.14 s to 0.40 s,
# while one with a request **in flight** does not honour SIGTERM at all (it logs "cleaning up
# before exit" and then blocks on the generation, the shipped tiers running --parallel 1), so it is
# killed and the whole grace is paid: 10.09 s and 10.90 s end to end on the stand-ins. So this is
# not slack that a fast idle stop makes generous; it is the real cost of evicting a busy tier, and
# tuning it down on the strength of the idle number would SIGKILL a model mid answer. A tier-scale
# model is the user's to re-measure (docs/runbooks/model-swap.md).
DEFAULT_STOP_GRACE_S = 10.0

# How long a SIGKILLed child gets to be reaped before the stop is reported as failed. A killed
# process only lingers in uninterruptible I/O, which on the model mount is possible, so this is a
# bound rather than an unbounded wait: the swap must be told rather than hang.
DEFAULT_REAP_TIMEOUT_S = 30.0

# How long the readiness probe's own client waits for a child's ``/health``. It is not spent by
# anything in this module, and it is still the supervisor's third bound: ``status`` probes inside
# the same per-model lock a ``stop`` takes, so a stop queued behind a status waits it out first.
# Measured: a status against a SIGSTOPped child took 5.80 s, and the stop behind it 15.70 s
# against 10.89 s with the lock free.
DEFAULT_PROBE_TIMEOUT_S = 5.0

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
        probe_timeout_s: float = DEFAULT_PROBE_TIMEOUT_S,
    ) -> None:
        self._roster = dict(roster)
        self._processes = processes
        self._probe = probe
        # All three, although only two are spent here: the probe's deadline belongs to the client
        # behind ``probe``, and this is the one object that can state the whole worst case of its
        # own slowest call, which is what the brain checks its control deadline against.
        self._bounds = ControlBounds(
            probe_timeout_s=probe_timeout_s,
            stop_grace_s=stop_grace_s,
            reap_timeout_s=reap_timeout_s,
        )
        # Which supervisor this is, minted per instance and therefore per daemon process. It
        # certifies the child table below: a brain that sees a value it has not seen before knows
        # that every belief it holds about what is resident was formed against a table that no
        # longer exists. Random rather than counted, because a counter in a process that restarted
        # begins again at exactly the number a reader is comparing to notice the restart.
        self._boot_id = uuid4().hex
        # A model is present here from the moment it is spawned until a stop has reaped it. A
        # present child with an exit code died unasked, which is the difference between FAILED
        # and STOPPED; the roster's own keys are the only ids that ever reach this dict.
        self._children: dict[str, ChildProcess] = {}
        self._locks = {model: asyncio.Lock() for model in self._roster}

    @property
    def models(self) -> tuple[str, ...]:
        """The logical ids this daemon serves, in roster order. Nothing can add to them."""
        return tuple(self._roster)

    @property
    def control_bounds(self) -> ControlBounds:
        """The three bounds this daemon was wired with, as ``GET /health`` reports them.

        On that route because the pairing a user has to keep (their sum below the brain's
        ``CORTEX_MODELHOST_TIMEOUT_S``) spans two containers' env, neither of which can read the
        other's: what a running daemon actually got is therefore an operator's question and the
        brain's, not an implementation detail.
        """
        return self._bounds

    @property
    def boot_id(self) -> str:
        """Which daemon this is, as ``GET /health`` names it, for the life of this process.

        Held here rather than in the API for the same reason the bounds are: this is the object
        whose in-memory child table the value certifies, and the route that publishes it is a
        serializer with no state of its own. Nothing in this process reads it back; its only
        consumer is a brain deciding whether what it believes about the GPU was believed about
        this daemon or about the one that ran before it.
        """
        return self._boot_id

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
                _logger.exception(
                    "a model process could not be stopped at shutdown", extra={"model": model}
                )

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
        if await self._reaped(child, self._bounds.stop_grace_s):
            return
        _logger.warning(
            "a model process ignored SIGTERM; killing it",
            extra={"model": model, "pid": child.pid, "grace_s": self._bounds.stop_grace_s},
        )
        child.kill()
        if await self._reaped(child, self._bounds.reap_timeout_s):
            return
        msg = (
            f"model {model!r} (pid {child.pid}) survived SIGKILL for "
            f"{self._bounds.reap_timeout_s}s; "
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
