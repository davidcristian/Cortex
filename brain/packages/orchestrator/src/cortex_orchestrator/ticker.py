"""ScheduleTicker: the stateless firing loop over the ScheduleStore (ADR-0025 decision 4).

One pass claims what is due (under the fencing lease), fires the batch concurrently, and
persists each outcome. The ticker itself holds nothing but its loop, so killing it anywhere
loses at most an in-flight fire, which the store's lease recovers (the one hard rule, live).
A ``REMINDER`` becomes deliverable and gets a push attempt (a failed push is just "pull will
deliver"); a ``TASK`` is dispatched as a synthetic ``spawn_subagents`` call through the
ticker's own audited dispatcher, giving the audit line, taint stamp (→ ADR-0017 roster pinning), and
the fail-closed ``confirmer=None`` gate all for free. Every pass is wrapped in a logged
catch-all (an unenumerated bug degrades to a skipped pass, never a silently dead ticker),
and shutdown is a stop signal, not a cancellation, so an in-flight pass finishes its fires
before the loop exits (``run_from_env`` keeps a bounded-grace forced cancel as the backstop).
"""

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
    """The poll loop: claim due items, fire them concurrently, persist the outcomes.

    ``spawn`` is the ticker's own audited dispatcher holding just the spawn tool (None =
    delegation not wired: a durable TASK from an earlier config fires an ``ok=False``
    outcome instead of crashing or lease-cycling); ``body`` is the push half (None = pull
    only). ``stop()`` ends the loop after the in-flight pass. The graceful path strands
    no claims because fires complete; the store's lease covers a forced cancel.
    """

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
        """Make the reminder deliverable, then attempt the push (ADR-0025 decisions 4-6).

        Finish-then-push: a crash between the two leaves the reminder deliverable for the
        pull path and never delivered-but-lost. A push the body confirmed shown is acked at
        once (a toast IS delivery); a fenced-off finish (cancel/re-claim won) pushes nothing.
        """
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
        """One subagent run via ``spawn_subagents``; failures become outcomes, never raises.

        ``dispatch(call, tainted=item.tainted)`` stamps the stored provenance onto the
        call (ADR-0018), so a tainted item's subagent is pinned to the injection-robust
        model by the roster (ADR-0017). The result's trust is the fire-time taint the
        store ORs onto the item. A clean-created task whose subagent read untrusted
        content cannot launder it into a trusted listing.
        """
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
