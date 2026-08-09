"""The residency record every other half reads: what the GPU serves, and who waits on it changing.
"""

import asyncio

from cortex_core.errors import HandoffInProgressError, ModelUnavailableError
from cortex_core.residency_state import RESIDENCY_SERVING, ResidencyReport


class ResidencyBoard:
    """Which model the GPU serves, what to tell a human about it, and the queue behind both."""

    def __init__(self, resident: str | None) -> None:
        self._condition = asyncio.Condition()
        self._resident = resident
        self._report: ResidencyReport = RESIDENCY_SERVING
        self._scope_model: str | None = None

    @property
    def condition(self) -> asyncio.Condition:
        """The one condition residency is published and waited on under.

        Handed to ``HandoffClaim`` so a claim and a scope can never be deciding about the same GPU
        at the same instant, which is the only reason it is exposed at all.
        """
        return self._condition

    @property
    def report(self) -> ResidencyReport:
        """What the GPU is serving right now, read synchronously and without touching the lock."""
        return self._report

    @property
    def scope_active(self) -> bool:
        """Whether a residency scope owns the card, for the callers that must stand down if so."""
        return self._scope_model is not None

    async def publish(self, model: str | None, report: ResidencyReport) -> None:
        """Publish which model the GPU serves (``None`` mid swap), and what to tell a human.

        The report is the one thing the resident cannot express on its own: a swap in and a swap
        back both leave nothing resident, so the direction is published rather than inferred.
        """
        async with self._condition:
            self._resident = model
            self._report = report
            self._condition.notify_all()

    async def publish_report(self, report: ResidencyReport) -> None:
        """Replace what a human is told, and leave what may be leased exactly where it is."""
        async with self._condition:
            self._report = report

    async def await_resident(self, model: str) -> None:
        """Wait out any scope this is not about, then refuse unless ``model`` is the resident."""
        async with self._condition:
            while self._scope_model is not None and self._scope_model != model:
                await self._condition.wait()
            if model != self._resident:
                msg = f"model {model!r} is not resident (resident: {self._resident!r})"
                raise ModelUnavailableError(msg)

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

    async def leave_scope(self) -> None:
        """Release the scope and wake every acquire that queued behind it."""
        async with self._condition:
            self._scope_model = None
            self._condition.notify_all()
