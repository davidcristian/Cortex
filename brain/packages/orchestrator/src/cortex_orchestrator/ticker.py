"""ScheduleTicker: the stateless firing loop over the ScheduleStore (ADR-0025 decision 4).

One pass claims what is due (under the fencing lease), fires the batch concurrently, and
persists each outcome. The ticker itself holds nothing but its loop, so killing it anywhere
loses at most an in-flight fire, which the store's lease recovers (the one hard rule, live).
A ``REMINDER`` becomes deliverable and gets a push attempt (a failed push is just "pull will
deliver"); a ``TASK`` is dispatched as a synthetic ``spawn_subagents`` call through the
ticker's own audited dispatcher, giving the audit line, taint stamp (→ ADR-0017 roster pinning), and
the fail-closed ``confirmer=None`` gate all for free, and its *outcome* then delivers as a
notification the same way a reminder's text does (ADR-0025 task-outcome addendum: finish
deliverable, push the outcome, let pull recover a body-down fire). Every pass is wrapped in a logged
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

# The toast titles; the body renders a title (and the reminder text or task outcome) as inert
# escaped text. A task's outcome delivers under its own title so the toast is honest about which
# it is (ADR-0025 task-outcome addendum).
REMINDER_TITLE = "Cortex reminder"
TASK_TITLE = "Cortex task"
_NO_RUNNER_OUTCOME = "FAILED: subagent delegation is not wired"


@dataclass(frozen=True, slots=True)
class TickerSettings:
    """The ticker's pacing and display zone, from ``ScheduleConfig`` (plain values below the edge).

    The zone rides here rather than as a constructor argument because the ticker is already at
    the six-argument injection ceiling, and because it arrives from exactly the same config
    object the pacing does. It is not a rendering concern on this path: a **calendar** item's
    re-arm is wall-clock arithmetic, so the ticker cannot compute where such an item fires next
    without knowing the zone (ADR-0025 calendar addendum). Interval items never consult it.
    """

    poll_s: float
    lease: timedelta
    claim_limit: int
    zone: DisplayZone = UTC_DISPLAY


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

        Each fire is bounded by the lease (post-review hardening): a hung fire (an
        unresponsive inference socket, a saturated admission budget) is cancelled by
        ``wait_for`` and its claim released, so one wedged task can never stall every
        later-due reminder for the process lifetime. ``release`` is fenced by the claim
        token, so releasing a claim whose fire already finished is a safe no-op. The
        pending set only avoids pointless round-trips.
        """
        now = self._clock.now()
        claims = await self._store.claim_due(
            now, lease=self._settings.lease, limit=self._settings.claim_limit
        )
        pending = {claim.token: claim for claim in claims}

        async def fire(claim: ScheduleClaim) -> None:
            await asyncio.wait_for(self._fire(claim), timeout=self._settings.lease.total_seconds())
            # Only reached when the fire persisted its outcome (or was fenced off).
            pending.pop(claim.token, None)

        try:
            results = await asyncio.gather(
                *(fire(claim) for claim in claims), return_exceptions=True
            )
            # Zipped rather than filtered: gather answers in the order it was given, so the
            # claim beside a failure is the item that failed, and a line that names it can be
            # followed to the reminder it is about.
            for claim, result in zip(claims, results, strict=True):
                if isinstance(result, BaseException):
                    _logger.error(
                        "schedule fire failed; the lease re-fires it",
                        exc_info=result,
                        extra={"reminder_id": claim.item.id},
                    )
        finally:
            for claim in pending.values():
                try:
                    await self._store.release(claim)
                except ScheduleStoreError:
                    _logger.exception(
                        "release failed; the lease recovers the claim",
                        extra={"reminder_id": claim.item.id},
                    )

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
            next_due=next_occurrence(item, fired_at, self._settings.zone),
            deliverable=True,
        )
        if await self._store.finish(claim, outcome):
            await self._deliver(item.id, title=REMINDER_TITLE, body=item.text, tainted=item.tainted)

    async def _deliver(self, item_id: str, *, title: str, body: str, tainted: bool) -> None:
        """Best-effort push of one fired item; any failure means the pull path delivers instead.

        The one ladder both kinds deliver through: a reminder pushes its text, a task its outcome.
        A push the body confirms ``shown`` is acked at once (a native toast IS delivery), so the
        pull surface will not show it again; a declined or failed push leaves the item deliverable
        for the next overlay open. That ack-or-stay-deliverable choice is the whole double-delivery
        defense on the happy path: exactly one of push and pull ever clears the deliverable slot,
        and the item survives a body-down fire (and a brain restart) in the store until it does
        (the one hard rule). A proactive re-push beyond this next-poll-pull is deferred: without a
        per-fire delivery id the body cannot tell a retry from a legitimate re-fire, so a re-push
        would turn the rare at-least-once duplicate into a common one (ADR-0025 retry addendum).
        """
        if self._body is None:
            return
        try:
            shown = await self._body.notify(
                title=title, body=body, reminder_id=item_id, tainted=tainted
            )
        except BodyGatewayError as err:
            _logger.info(
                "push failed; pull will deliver",
                extra={"reminder_id": item_id, "error": str(err)},
            )
            return
        if shown:
            await self._store.ack(item_id)

    async def _fire_task(self, claim: ScheduleClaim, item: ScheduledItem) -> None:
        """Run the task, persist its outcome deliverable, then deliver the outcome as a toast.

        A finished task's outcome delivers as a notification exactly as a reminder does: ``finish``
        stamps it deliverable (so a body-down fire is recovered by pull, not lost, and a one-shot
        task's outcome now survives its fire instead of being deleted with the record), and the
        push carries the *outcome*, never the standing instruction. A fenced-off finish (cancel or
        re-claim won) delivers nothing, the reminder path's rule.
        """
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
                item.id, title=TASK_TITLE, body=outcome_text, tainted=item.tainted or fire_tainted
            )

    async def _run_task(self, item: ScheduledItem) -> tuple[str, bool]:
        """One subagent run via ``spawn_subagents``; failures become outcomes, never raises.

        The dispatch stamp carries the item's stored provenance (ADR-0018/0027): its taint,
        so a tainted item's subagent is pinned to the injection-robust model by the roster
        (ADR-0017), and its origin ``session_id``, which the spawn tool now writes onto each
        task and the audit trail prints, so a fired item's delegated tool calls name the chat
        that scheduled them (ADR-0009 named-work addendum). The stamp names no turn, because a
        fire is not one: nothing conversational is waiting on it, so the trail says so by
        leaving the field off rather than by borrowing an id. The result's trust is the
        fire-time taint the store ORs onto the item. A clean-created task whose subagent read
        untrusted content cannot launder it into a trusted listing.
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
            result = await self._spawn.dispatch(
                call, stamp=TurnStamp(session_id=item.session_id, tainted=item.tainted)
            )
        except TaskStoreError as err:
            return f"FAILED: the task store is unavailable: {err}", False
        text = result.content if not result.is_error else f"FAILED: {result.content}"
        return text, result.trust is Trust.UNTRUSTED
