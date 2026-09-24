"""The residency bookkeeping the swap publishes into: what the GPU serves, and who waits on it."""

import asyncio

from cortex_core.errors import HandoffInProgressError, ModelUnavailableError
from cortex_core.residency_state import RESIDENCY_SERVING, Fence, ResidencyReport


class ResidencyBoard:
    """Which model the GPU serves, what to tell a human about it, and the queue behind both."""

    def __init__(self, resident: str | None) -> None:
        self._condition = asyncio.Condition()
        self._resident = resident
        self._report: ResidencyReport = RESIDENCY_SERVING
        self._scope_model: str | None = None
        self._scope_task: asyncio.Task[object] | None = None

    @property
    def condition(self) -> asyncio.Condition:
        """The one condition residency is published and waited on under."""
        return self._condition

    @property
    def report(self) -> ResidencyReport:
        """What the GPU is serving right now, read synchronously and without touching the lock."""
        return self._report

    @property
    def scope_active(self) -> bool:
        """Whether a residency scope owns the card, for the callers that must back off if so."""
        return self._scope_model is not None

    async def publish(self, model: str | None, report: ResidencyReport) -> None:
        """Publish which model the GPU serves (``None`` mid swap), and what to tell a human."""
        async with self._condition:
            self._write(model, report)

    async def publish_between_handoffs(
        self, model: str | None, report: ResidencyReport, fence: Fence
    ) -> bool:
        """Publish only while nothing owns the GPU, and return whether the write happened."""
        async with self._condition:
            if not fence():
                return False
            self._write(model, report)
            return True

    def _write(self, model: str | None, report: ResidencyReport) -> None:
        """Set both fields together, then wake the queue."""
        self._resident = model
        self._report = report
        self._condition.notify_all()

    async def publish_report(self, report: ResidencyReport) -> None:
        """Replace what a human is told, and leave what may be leased where it is."""
        async with self._condition:
            self._report = report

    def blocks(self, model: str) -> bool:
        """Whether a scope about another model is active, so leasing ``model`` would queue."""
        return self._scope_model is not None and self._scope_model != model

    async def await_scope_end(self, model: str) -> None:
        """Wait out any scope this is not about, and leave the residency check to the lease."""
        async with self._condition:
            await self._wait_out_scope(model)

    async def await_resident(self, model: str) -> None:
        """Wait out any scope this is not about, then raise unless ``model`` is the resident."""
        async with self._condition:
            await self._wait_out_scope(model)
            if model != self._resident:
                msg = f"model {model!r} is not resident (resident: {self._resident!r})"
                raise ModelUnavailableError(msg)

    async def _wait_out_scope(self, model: str) -> None:
        """Wait, under the condition, until no scope about another model is active."""
        if self.blocks(model) and asyncio.current_task() is self._scope_task:
            # The scope ends only when this task leaves it, so this wait could never end.
            msg = (
                f"model {model!r} was asked for inside the residency scope for "
                f"{self._scope_model!r}, which only that model may be leased in"
            )
            raise ModelUnavailableError(msg)
        while self.blocks(model):
            await self._condition.wait()

    async def enter_scope(self, model: str) -> None:
        """Claim the one residency scope, so every other model's acquire starts queuing."""
        async with self._condition:
            if self._scope_model is not None:
                msg = (
                    f"a residency scope for {self._scope_model!r} is already active, so "
                    f"{model!r} cannot be swapped in (there is one GPU)"
                )
                raise HandoffInProgressError(msg)
            self._scope_model = model
            self._scope_task = asyncio.current_task()

    async def leave_scope(self) -> None:
        """Release the scope and wake every acquire that queued behind it."""
        async with self._condition:
            self._scope_model = None
            self._condition.notify_all()
