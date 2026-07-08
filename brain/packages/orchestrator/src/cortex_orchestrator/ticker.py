"""ScheduleTicker: the stateless firing loop over the ScheduleStore (ADR-0025 decision 4)."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from cortex_core import (
    SPAWN_TOOL_NAME,
    BodyGateway,
    BodyGatewayError,
    Clock,
    FireOutcome,
    ScheduleClaim,
    ScheduledItem,
    ScheduleKind,
    ScheduleStore,
    ScheduleStoreError,
    TaskStoreError,
    ToolCall,
    ToolDispatcher,
    Trust,
    next_due,
)

_logger = logging.getLogger(__name__)

# The toast's title; the body renders it (and the reminder text) as inert escaped text.
REMINDER_TITLE = "Cortex reminder"
_NO_RUNNER_OUTCOME = "FAILED: subagent delegation is not wired"


@dataclass(frozen=True, slots=True)
class TickerSettings:
    """The ticker's pacing, from ``ScheduleConfig`` (plain values below the edge)."""

    poll_s: float
    lease: timedelta
    claim_limit: int


class ScheduleTicker:
    """The poll loop: claim due items, fire them concurrently, persist the outcomes."""

    def __init__(
        self,
        store: ScheduleStore,
        clock: Clock,
        settings: TickerSettings,
        *,
        spawn: ToolDispatcher | None = None,
        body: BodyGateway | None = None,
    ) -> None:
        self._store = store
        self._clock = clock
        self._settings = settings
        self._spawn = spawn
        self._body = body
        self._stopping = asyncio.Event()

    def stop(self) -> None:
        """Ask the loop to end after the in-flight pass (idempotent, sync, signal-safe)."""
        self._stopping.set()

    async def run(self) -> None:
        """Poll until stopped; a failing pass is logged and retried next poll, never fatal."""
        while not self._stopping.is_set():
            try:
                await self.run_once()
            except Exception:
                # The ADR-0025 pass guard: an unenumerated bug degrades to a skipped
                # pass (logged), never a silently dead ticker.
                _logger.exception("schedule pass failed; the next poll retries")
            # Wake early on stop(); otherwise pace the next pass. wait_for cancels the
            # inner wait on timeout. The loop condition then decides.
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._settings.poll_s)
            except TimeoutError:
                continue

    async def run_once(self) -> None:
        """One stateless pass: claim → fire concurrently → persist; release what didn't finish.

        ``release`` is fenced by the claim token, so releasing a claim whose fire already
        finished is a safe no-op. The pending set only avoids pointless round-trips.
        """
        now = self._clock.now()
        claims = await self._store.claim_due(
            now, lease=self._settings.lease, limit=self._settings.claim_limit
        )
        pending = {claim.token: claim for claim in claims}

        async def fire(claim: ScheduleClaim) -> None:
            await self._fire(claim)
            # Only reached when the fire persisted its outcome (or was fenced off).
            pending.pop(claim.token, None)

        try:
            results = await asyncio.gather(
                *(fire(claim) for claim in claims), return_exceptions=True
            )
            for failure in (r for r in results if isinstance(r, BaseException)):
                _logger.error("schedule fire failed; the lease re-fires it", exc_info=failure)
        finally:
            for claim in pending.values():
                try:
                    await self._store.release(claim)
                except ScheduleStoreError:
                    _logger.exception("release failed; the lease recovers the claim")

    async def _fire(self, claim: ScheduleClaim) -> None:
        """Fire one claimed item and persist its outcome under the fencing token."""
        item = claim.item
        if item.kind is ScheduleKind.REMINDER:
            await self._fire_reminder(claim, item)
        else:
            await self._fire_task(claim, item)

    async def _fire_reminder(self, claim: ScheduleClaim, item: ScheduledItem) -> None:
        """Make the reminder deliverable, then attempt the push (ADR-0025 decisions 4-6)."""
        fired_at = self._clock.now()
        outcome = FireOutcome(
            fired_at=fired_at,
            next_due=next_due(item.due_at, item.every, fired_at),
            deliverable=True,
        )
        if await self._store.finish(claim, outcome):
            await self._push(item)

    async def _push(self, item: ScheduledItem) -> None:
        """Best-effort push; any failure means the pull path delivers instead."""
        if self._body is None:
            return
        try:
            shown = await self._body.notify(
                title=REMINDER_TITLE, body=item.text, reminder_id=item.id, tainted=item.tainted
            )
        except BodyGatewayError as err:
            _logger.info(
                "reminder push failed; pull will deliver",
                extra={"reminder_id": item.id, "error": str(err)},
            )
            return
        if shown:
            await self._store.ack(item.id)

    async def _fire_task(self, claim: ScheduleClaim, item: ScheduledItem) -> None:
        """Run the task as an audited spawn dispatch and persist its outcome + fire taint."""
        outcome_text, fire_tainted = await self._run_task(item)
        fired_at = self._clock.now()
        await self._store.finish(
            claim,
            FireOutcome(
                fired_at=fired_at,
                next_due=next_due(item.due_at, item.every, fired_at),
                deliverable=False,
                outcome=outcome_text,
                tainted=fire_tainted,
            ),
        )

    async def _run_task(self, item: ScheduledItem) -> tuple[str, bool]:
        """One subagent run via ``spawn_subagents``; failures become outcomes, never raises."""
        if self._spawn is None:
            return _NO_RUNNER_OUTCOME, False
        instruction: dict[str, str] = {"instruction": item.text}
        if item.model:
            instruction["model"] = item.model
        call = ToolCall(
            id=f"schedule-{item.id}",
            name=SPAWN_TOOL_NAME,
            arguments={"instructions": [instruction]},
        )
        try:
            result = await self._spawn.dispatch(call, tainted=item.tainted)
        except TaskStoreError as err:
            return f"FAILED: the task store is unavailable: {err}", False
        text = result.content if not result.is_error else f"FAILED: {result.content}"
        return text, result.trust is Trust.UNTRUSTED
