"""Scriptable ``ModelHost`` twin: start, stop, and probe models that do not exist (ADR-0030).

The fake the ADR mandates for CI and the chaos suite, in ``src`` rather than a test tree because
it is the reference implementation of the port and is gated like one. It models exactly what a
real supervisor can do to a swap and nothing more: an operation can fail permanently or once, a
started model can report any state (never coming ready, or coming back FAILED), and any single
operation can be **paused at its boundary** so a test kills the conductor precisely there. Each
knob exists for a named kill point of the swap sequence; there are no speculative ones.

``calls`` is the op log, in order, which is what proves a swap requested the right things in the
right order (and requested them at most once).
"""

import asyncio
from collections.abc import Iterable, Mapping

from cortex_core.errors import ModelHostError
from cortex_core.model_host import ControlBounds, DeviceMemory, ModelHostState


class ScriptedModelHost:
    """ModelHost twin holding a set of running models, with scripted failures and pauses.

    ``running`` seeds which models are up (a boot default of the cortex, as the real sidecar
    has). ``status_override`` is what a **running** model reports instead of ``READY``, which is
    how a model that never finishes loading (``LOADING``) or that died at load (``FAILED``) is
    scripted. ``fail`` raises ``ModelHostError`` for an ``(op, model)`` pair every time and
    ``fail_once`` for its first occurrence only, which is what the restore's retry is tested
    against. ``pause_at`` names the ``(op, model)`` pairs whose effect lands and then blocks
    until released: ``reached[key]`` fires when the boundary is entered and the call resumes
    when ``release[key]`` is set, so a test can cancel the swap at exactly that point.

    Effects apply before a pause and after a failure check: a failed ``start`` starts nothing,
    while a paused ``stop`` has genuinely stopped its model, which is what makes a kill at that
    boundary the honest analogue of a process death after the eviction.

    ``device_memory`` is the card this twin claims to sit beside, and ``None`` (the default) is
    the honest answer for a twin that starts no process on any GPU: it says "this host cannot see
    a card", which is what the scripted backend genuinely cannot. A test that needs a swap to get
    past a fit check hands it a reading, and one that needs the fail-closed path leaves it out.
    The reading is a fixed value rather than a ledger over ``running``, deliberately: this twin
    models the port, and modelling VRAM arithmetic here would invent numbers no measurement
    backs.

    ``control_bounds`` is the same shape once more, and ``None`` (the default) is again the honest
    answer: a twin whose ``stop`` is a set removal has no SIGTERM grace and no reap to bound, so
    the composition root's pairing check finds nothing to compare and says so. A test that needs
    the check to have something to compare hands it bounds.
    """

    def __init__(  # noqa: PLR0913 -- one knob per scripted condition, all keyword-only
        self,
        *,
        running: Iterable[str] = (),
        status_override: Mapping[str, ModelHostState] | None = None,
        fail: Mapping[tuple[str, str], str] | None = None,
        fail_once: Mapping[tuple[str, str], str] | None = None,
        pause_at: Iterable[tuple[str, str]] = (),
        device_memory: DeviceMemory | None = None,
        control_bounds: ControlBounds | None = None,
    ) -> None:
        self.running: set[str] = set(running)
        self.device: DeviceMemory | None = device_memory
        self.bounds: ControlBounds | None = control_bounds
        self.calls: list[tuple[str, str]] = []
        self.reached: dict[tuple[str, str], asyncio.Event] = {
            key: asyncio.Event() for key in pause_at
        }
        self.release: dict[tuple[str, str], asyncio.Event] = {
            key: asyncio.Event() for key in self.reached
        }
        self._override = dict(status_override or {})
        self._fail = dict(fail or {})
        self._fail_once = dict(fail_once or {})

    def set_status(self, model: str, state: ModelHostState | None) -> None:
        """Change what a **running** ``model`` reports, or clear the override with ``None``.

        The constructor's ``status_override`` says what a model reports from the start; this says
        it later, which is what the shared ``ModelHost`` contract suite needs to drive both this
        twin and the real supervisor adapter through the same script. A load that has not finished
        (``LOADING``) and a process that died unasked (``FAILED``) are conditions of the world,
        not of the port, so the suite arranges them here and asserts what ``status`` then answers.
        """
        if state is None:
            self._override.pop(model, None)
            return
        self._override[model] = state

    async def start(self, model: str) -> None:
        """Begin loading ``model`` (idempotent); the model reports its scripted state after."""
        self._check("start", model)
        self.running.add(model)
        await self._pause("start", model)

    async def stop(self, model: str) -> None:
        """Stop ``model`` (idempotent); a stopped model reports ``STOPPED``."""
        self._check("stop", model)
        self.running.discard(model)
        await self._pause("stop", model)

    async def status(self, model: str) -> ModelHostState:
        """Report what ``model`` is doing: ``STOPPED``, or its override, or ``READY``."""
        self._check("status", model)
        await self._pause("status", model)
        if model not in self.running:
            return ModelHostState.STOPPED
        return self._override.get(model, ModelHostState.READY)

    async def device_memory(self) -> DeviceMemory | None:
        """What the card beside this twin reports, or ``None`` for a host that sees none.

        Logged in ``calls`` under an empty id, since the reading is about the host and not about
        any one model, and scriptable for failure and pause through that same key: the fit check
        runs inside the swap's own try, so a host that cannot answer must be able to fail there.
        """
        self._check("device_memory", "")
        await self._pause("device_memory", "")
        return self.device

    async def control_bounds(self) -> ControlBounds | None:
        """The stop timing this twin claims to have been wired with, or ``None`` for none.

        Logged and scriptable under an empty id like the card reading, and for the same reason:
        the composition root asks this of a host that may be unreachable, so a twin that could
        not refuse would leave that path untestable over fakes.
        """
        self._check("control_bounds", "")
        await self._pause("control_bounds", "")
        return self.bounds

    def _check(self, op: str, model: str) -> None:
        """Log the operation, then raise whatever failure was scripted for it."""
        key = (op, model)
        self.calls.append(key)
        if (once := self._fail_once.pop(key, None)) is not None:
            raise ModelHostError(once)
        if (always := self._fail.get(key)) is not None:
            raise ModelHostError(always)

    async def _pause(self, op: str, model: str) -> None:
        """Block at this operation's boundary when one was armed, else return at once."""
        gate = self.reached.get((op, model))
        if gate is None:
            return
        gate.set()
        await self.release[(op, model)].wait()
