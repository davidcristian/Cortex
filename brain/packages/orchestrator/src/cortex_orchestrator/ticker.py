"""ScheduleTicker: the stateless firing loop over the ScheduleStore."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from cortex_core import (
    SPAWN_TOOL_NAME,
    UTC_DISPLAY,
    BodyGateway,
    BodyGatewayError,
    Clock,
    DisplayZone,
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
    TurnStamp,
    next_occurrence,
)

_logger = logging.getLogger(__name__)

REMINDER_TITLE = "Cortex reminder"
TASK_TITLE = "Cortex task"
_NO_RUNNER_OUTCOME = "FAILED: subagent delegation is not wired"


@dataclass(frozen=True, slots=True)
class TickerSettings:
    """The ticker's pacing and display zone, as the plain values below the edge take them."""

    poll_s: float
    lease: timedelta
    claim_limit: int
    zone: DisplayZone = UTC_DISPLAY


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
        """Signal the loop to end after the in-flight pass (idempotent, sync, signal-safe)."""
        self._stopping.set()

    async def run(self) -> None:
        """Poll until stopped; a failing pass is logged and retried next poll, never fatal."""
        while not self._stopping.is_set():
            try:
                await self.run_once()
            except Exception:  # deliberately broad: one bug costs a pass, never the loop
                _logger.exception("schedule pass failed; the next poll retries")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._settings.poll_s)
            except TimeoutError:
                continue

    async def run_once(self) -> None:
        """One stateless pass: claim, fire concurrently, persist; release what didn't finish."""
        now = self._clock.now()
        claims = await self._store.claim_due(
            now, lease=self._settings.lease, limit=self._settings.claim_limit
        )
        pending = {claim.token: claim for claim in claims}

        async def fire(claim: ScheduleClaim) -> None:
            await asyncio.wait_for(self._fire(claim), timeout=self._settings.lease.total_seconds())
            pending.pop(claim.token, None)

        try:
            results = await asyncio.gather(
                *(fire(claim) for claim in claims), return_exceptions=True
            )
            # Zipped rather than filtered: gather answers in the order it was given, so the
            # claim beside a failure is the item that failed and the line can name it.
            for claim, result in zip(claims, results, strict=True):
                if isinstance(result, BaseException):
                    _logger.error(
                        "schedule fire failed; the lease re-fires it",
                        exc_info=result,
                        extra={"item_id": claim.item.id},
                    )
        finally:
            for claim in pending.values():
                try:
                    await self._store.release(claim)
                except ScheduleStoreError:
                    _logger.exception(
                        "release failed; the lease recovers the claim",
                        extra={"item_id": claim.item.id},
                    )

    async def _fire(self, claim: ScheduleClaim) -> None:
        """Fire one claimed item and persist its outcome under the fencing token."""
        item = claim.item
        if item.kind is ScheduleKind.REMINDER:
            await self._fire_reminder(claim, item)
        else:
            await self._fire_task(claim, item)

    async def _fire_reminder(self, claim: ScheduleClaim, item: ScheduledItem) -> None:
        """Make the reminder deliverable, then attempt the push."""
        fired_at = self._clock.now()
        outcome = FireOutcome(
            fired_at=fired_at,
            next_due=next_occurrence(item, fired_at, self._settings.zone),
            deliverable=True,
        )
        if await self._store.finish(claim, outcome):
            await self._deliver(
                item.id, fired_at, title=REMINDER_TITLE, body=item.text, tainted=item.tainted
            )

    async def _deliver(
        self, item_id: str, fired_at: datetime, *, title: str, body: str, tainted: bool
    ) -> None:
        """Best-effort push of one fired item; any failure means the pull path delivers instead."""
        if self._body is None:
            return
        try:
            shown = await self._body.notify(
                title=title, body=body, reminder_id=item_id, tainted=tainted
            )
        except BodyGatewayError as err:
            _logger.info(
                "push failed; pull will deliver",
                extra={"item_id": item_id, "error": str(err)},
            )
            return
        if shown:
            await self._store.ack(item_id, fired_at=fired_at)

    async def _fire_task(self, claim: ScheduleClaim, item: ScheduledItem) -> None:
        """Run the task, persist its outcome deliverable, then deliver the outcome as a toast."""
        outcome_text, fire_tainted = await self._run_task(item)
        fired_at = self._clock.now()
        outcome = FireOutcome(
            fired_at=fired_at,
            next_due=next_occurrence(item, fired_at, self._settings.zone),
            deliverable=True,
            outcome=outcome_text,
            tainted=fire_tainted,
        )
        if await self._store.finish(claim, outcome):
            await self._deliver(
                item.id,
                fired_at,
                title=TASK_TITLE,
                body=outcome_text,
                tainted=item.tainted or fire_tainted,
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
            result = await self._spawn.dispatch(
                call,
                stamp=TurnStamp(session_id=item.session_id, item_id=item.id, tainted=item.tainted),
            )
        except TaskStoreError as err:
            return f"FAILED: the task store is unavailable: {err}", False
        text = result.content if not result.is_error else f"FAILED: {result.content}"
        return text, result.trust is Trust.UNTRUSTED
