"""Scriptable ``ModelHost``: start, stop, and check models, including ones that do not exist."""

import asyncio
from collections.abc import Iterable, Mapping

from cortex_core.errors import ModelHostError, ModelNotHostedError
from cortex_core.model_host import ControlBounds, DeviceMemory, ModelHostState


class ScriptedModelHost:
    """ModelHost twin holding a set of running models, with scripted failures and pauses."""

    def __init__(  # noqa: PLR0913 -- one argument per scripted condition, all keyword-only
        self,
        *,
        running: Iterable[str] = (),
        status_override: Mapping[str, ModelHostState] | None = None,
        fail: Mapping[tuple[str, str], str] | None = None,
        fail_once: Mapping[tuple[str, str], str] | None = None,
        pause_at: Iterable[tuple[str, str]] = (),
        unhosted: Iterable[str] = (),
        device_memory: DeviceMemory | None = None,
        control_bounds: ControlBounds | None = None,
        boot_id: str | None = None,
    ) -> None:
        self.running: set[str] = set(running)
        self.unhosted: set[str] = set(unhosted)
        self.device: DeviceMemory | None = device_memory
        self.bounds: ControlBounds | None = control_bounds
        self.boot: str | None = boot_id
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
        """Change what a **running** ``model`` reports, or clear the override with ``None``."""
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
        """What the card beside this twin reports, or ``None`` for a host that sees none."""
        self._check("device_memory", "")
        await self._pause("device_memory", "")
        return self.device

    async def control_bounds(self) -> ControlBounds | None:
        """The stop timing this twin claims to have been wired with, or ``None`` for none."""
        self._check("control_bounds", "")
        await self._pause("control_bounds", "")
        return self.bounds

    async def boot_id(self) -> str | None:
        """Which daemon this twin claims to be, or ``None`` for one that will not say."""
        self._check("boot_id", "")
        await self._pause("boot_id", "")
        return self.boot

    def _check(self, op: str, model: str) -> None:
        """Log the operation, then raise whatever failure was scripted for it."""
        key = (op, model)
        self.calls.append(key)
        if model in self.unhosted:
            msg = f"unknown model {model!r}; this twin was told it does not host it"
            raise ModelNotHostedError(msg)
        if (once := self._fail_once.pop(key, None)) is not None:
            raise ModelHostError(once)
        if (always := self._fail.get(key)) is not None:
            raise ModelHostError(always)

    async def _pause(self, op: str, model: str) -> None:
        """Block at this operation's boundary when one was set up, else return at once."""
        gate = self.reached.get((op, model))
        if gate is None:
            return
        gate.set()
        await self.release[(op, model)].wait()
