"""The residency bookkeeping the swap publishes into: what the GPU serves, and who waits on it.

``residency_moves.py`` owns what the host is asked to do and ``residency_restore.py`` owns what the
swap back promises; both publish here. ``SwappingModelManager`` keeps what neither a move nor this
record can decide: when the GPU may change hands, and the lease every move runs under.

These four facts are one object because of one invariant: the resident and the report are published
together, under one condition and with nothing awaited between them, so the lease's view of the GPU
and the seam's answer about it cannot drift apart. ``publish_report`` is the one exception, a
separate verb because a report written without a resident is a claim about what to display and not
about what may be leased. ``publish_between_handoffs`` adds a condition on when the write may
happen, and is a verb here rather than a check at its caller because only a write that tests the
fence under this object's own condition can be sure a handoff did not begin in between
(``residency_regain.py``).

The scope flag lives here too, since an acquire of a model no active scope is about waits on this
same condition rather than failing, and the scope's end is the only thing that wakes it. Reading
the report takes no lock, because the seam probes it every few seconds while a swap holds
everything else.
"""

import asyncio

from cortex_core.errors import HandoffInProgressError, ModelUnavailableError
from cortex_core.residency_state import RESIDENCY_SERVING, Fence, ResidencyReport


class ResidencyBoard:
    """Which model the GPU serves, what to tell a human about it, and the queue behind both.

    ``resident`` seeds a fresh manager with the standing residency. The seed is an assumption, so
    boot recovery republishes it from an observation before the seam serves anything.
    """

    def __init__(self, resident: str | None) -> None:
        self._condition = asyncio.Condition()
        self._resident = resident
        self._report: ResidencyReport = RESIDENCY_SERVING
        self._scope_model: str | None = None

    @property
    def condition(self) -> asyncio.Condition:
        """The one condition residency is published and waited on under.

        Exposed only so ``HandoffClaim`` can share it, which is what keeps a claim and a scope from
        deciding about the same GPU at the same instant.
        """
        return self._condition

    @property
    def report(self) -> ResidencyReport:
        """What the GPU is serving right now, read synchronously and without touching the lock.

        A plain read is a consistent snapshot precisely because every writer below publishes the
        report and the resident together: there is no instant at which one has landed and the
        other has not.
        """
        return self._report

    @property
    def scope_active(self) -> bool:
        """Whether a residency scope owns the card, for the callers that must back off if so."""
        return self._scope_model is not None

    async def publish(self, model: str | None, report: ResidencyReport) -> None:
        """Publish which model the GPU serves (``None`` mid swap), and what to tell a human.

        The report is the one thing the resident cannot express on its own: a swap in and a swap
        back both leave nothing resident, so the direction is published rather than inferred.
        """
        async with self._condition:
            self._write(model, report)

    async def publish_between_handoffs(
        self, model: str | None, report: ResidencyReport, fence: Fence
    ) -> bool:
        """Publish only while nothing owns the GPU, and return whether the write landed.

        The background pass's writer (``residency_regain.py``). It is a verb of its own rather than
        a check the caller makes before ``publish`` because that pass reads the machine over
        several awaits, so a handoff can begin between what it observed and what it concludes, and
        a publish ordered after such a check would overwrite the swap's own report with a reading
        taken before the swap started. The fence is therefore read here, under this condition,
        which is the one ``HandoffClaim`` sets its flag under and ``enter_scope`` sets the scope
        under, with nothing awaited between the answer and the write. A handoff either loses the
        race and finds the report already published, or wins it and this returns ``False``.

        This is in-process ordering only, like every other guard here: it settles two coroutines of
        this process and says nothing about a second process (ADR-0030 fenced-claim addendum).
        """
        async with self._condition:
            if not fence():
                return False
            self._write(model, report)
            return True

    def _write(self, model: str | None, report: ResidencyReport) -> None:
        """Land both fields together, then wake the queue.

        Always called with the condition already held, which is what makes "nothing awaited between
        them" a property of this object rather than of each caller.
        """
        self._resident = model
        self._report = report
        self._condition.notify_all()

    async def publish_report(self, report: ResidencyReport) -> None:
        """Replace what a human is told, and leave what may be leased where it is.

        Boot recovery's publish and nothing else. Failing to confirm the cortex is not the same as
        confirming it is gone, so the report is updated while the lease keeps boot recovery's
        forgiving posture.
        """
        async with self._condition:
            self._report = report

    async def await_resident(self, model: str) -> None:
        """Wait out any scope this is not about, then raise unless ``model`` is the resident.

        The wait is what makes a queued cortex turn survive a handoff instead of failing: an
        acquire that arrives mid swap blocks until the scope ends and then runs. A scope for
        ``model`` itself is not waited on, since that is the deep model leasing its own residency.
        """
        async with self._condition:
            while self._scope_model is not None and self._scope_model != model:
                await self._condition.wait()
            if model != self._resident:
                msg = f"model {model!r} is not resident (resident: {self._resident!r})"
                raise ModelUnavailableError(msg)

    async def enter_scope(self, model: str) -> None:
        """Claim the one residency scope, so every other model's acquire starts queuing.

        The backstop under ``HandoffClaim``: a caller that swaps without claiming first still
        raises, and with the same typed error, because a second swap is a second handoff however it
        was reached rather than a swap that broke.
        """
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
