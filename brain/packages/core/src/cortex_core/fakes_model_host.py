"""Scriptable ``ModelHost`` twin: start, stop, and probe models that do not exist (ADR-0030)."""

import asyncio
from collections.abc import Iterable, Mapping

from cortex_core.errors import ModelHostError
from cortex_core.model_host import ModelHostState


class ScriptedModelHost:
    """ModelHost twin holding a set of running models, with scripted failures and pauses."""

    def __init__(
        self,
        *,
        running: Iterable[str] = (),
        status_override: Mapping[str, ModelHostState] | None = None,
        fail: Mapping[tuple[str, str], str] | None = None,
        fail_once: Mapping[tuple[str, str], str] | None = None,
        pause_at: Iterable[tuple[str, str]] = (),
    ) -> None:
        self.running: set[str] = set(running)
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
