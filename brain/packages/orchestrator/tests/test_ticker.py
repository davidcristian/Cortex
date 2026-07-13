"""The ScheduleTicker: fires, pushes, re-arms, releases, and survives its own passes
(ADR-0025 decision 4). No wall-clock waits. The clock is fixed and `run` is paced to 0."""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from cortex_core import (
    BodyGatewayError,
    CompositeToolRegistry,
    FireOutcome,
    InMemoryBodyGateway,
    InMemoryScheduleStore,
    RecordingAuditSink,
    ScheduleClaim,
    ScheduledItem,
    ScheduleKind,
    ScheduleStoreError,
    TaskStoreError,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolSpec,
    Trust,
    TurnStamp,
)
from cortex_orchestrator import REMINDER_TITLE, ScheduleTicker, TickerSettings

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
_SETTINGS = TickerSettings(poll_s=0.001, lease=timedelta(minutes=5), claim_limit=8)


class FixedClock:
    def now(self) -> datetime:
        return _NOW


class FakeSpawnTool:
    """A scripted `spawn_subagents` builtin: records the dispatched calls it receives."""

    def __init__(
        self,
        *,
        content: str = "[subagent 1] ok",
        trust: Trust = Trust.TRUSTED,
        is_error: bool = False,
        raise_task_store: bool = False,
    ) -> None:
        self._content = content
        self._trust = trust
        self._is_error = is_error
        self._raise = raise_task_store
        self.calls: list[ToolCall] = []

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(name="spawn_subagents", description="fake", parameters={"type": "object"})

    async def invoke(self, call: ToolCall) -> ToolResult:
        self.calls.append(call)
        if self._raise:
            msg = "redis down"
            raise TaskStoreError(msg)
        return ToolResult(
            call_id=call.id, content=self._content, is_error=self._is_error, trust=self._trust
        )


def _dispatcher(tool: FakeSpawnTool) -> ToolDispatcher:
    return ToolDispatcher(CompositeToolRegistry([tool]), RecordingAuditSink(), FixedClock())


def _item(
    item_id: str,
    *,
    kind: ScheduleKind = ScheduleKind.REMINDER,
    every: timedelta | None = None,
    model: str = "",
    tainted: bool = False,
) -> ScheduledItem:
    return ScheduledItem(
        id=item_id,
        kind=kind,
        text=f"text of {item_id}",
        session_id="chat-1",
        due_at=_NOW,
        created_at=_NOW,
        every=every,
        model=model,
        tainted=tainted,
    )


def _ticker(
    store: InMemoryScheduleStore,
    *,
    spawn: ToolDispatcher | None = None,
    body: InMemoryBodyGateway | None = None,
) -> ScheduleTicker:
    return ScheduleTicker(store, FixedClock(), _SETTINGS, spawn=spawn, body=body)


# --- reminders: deliverable + the push ladder --------------------------------------------------


async def test_reminder_fires_to_deliverable_without_a_body() -> None:
    store = InMemoryScheduleStore()
    await store.add(_item("r1"))
    await _ticker(store).run_once()
    (due,) = await store.deliverable()
    assert due.id == "r1"
    assert due.deliverable_since == _NOW


async def test_pushed_and_shown_reminder_is_acked_at_once() -> None:
    store = InMemoryScheduleStore()
    body = InMemoryBodyGateway(shown=True)
    await store.add(_item("r1", tainted=True))
    await _ticker(store, body=body).run_once()
    assert await store.deliverable() == ()  # a toast IS delivery
    (toast,) = body.notifications
    assert toast.title == REMINDER_TITLE
    assert toast.body == "text of r1"
    assert toast.reminder_id == "r1"
    assert toast.tainted is True


async def test_push_declined_leaves_the_reminder_for_pull() -> None:
    store = InMemoryScheduleStore()
    body = InMemoryBodyGateway(shown=False)
    await store.add(_item("r1"))
    await _ticker(store, body=body).run_once()
    (due,) = await store.deliverable()
    assert due.id == "r1"


async def test_push_failure_leaves_the_reminder_for_pull() -> None:
    store = InMemoryScheduleStore()
    body = InMemoryBodyGateway(fail=BodyGatewayError("unreachable"))
    await store.add(_item("r1"))
    await _ticker(store, body=body).run_once()
    (due,) = await store.deliverable()
    assert due.id == "r1"


async def test_recurring_reminder_rearms_and_stays_deliverable() -> None:
    store = InMemoryScheduleStore()
    await store.add(_item("r1", every=timedelta(hours=1)))
    await _ticker(store).run_once()
    loaded = await store.get("r1")
    assert loaded is not None
    assert loaded.due_at == _NOW + timedelta(hours=1)
    assert loaded.deliverable_since == _NOW


async def test_recurring_rearm_follows_the_snooze_anchor_grid() -> None:
    """A snoozed recurring item re-arms on its original cadence, not due_at + every."""
    store = InMemoryScheduleStore()
    anchor = _NOW - timedelta(minutes=90)  # grid anchor + k*1h lands next at _NOW + 30min
    await store.add(
        ScheduledItem(
            id="r1",
            kind=ScheduleKind.REMINDER,
            text="text of r1",
            session_id="chat-1",
            due_at=_NOW,  # the snoozed occurrence, deliberately off the anchor grid
            created_at=_NOW,
            every=timedelta(hours=1),
            anchor=anchor,
        )
    )
    await _ticker(store).run_once()
    loaded = await store.get("r1")
    assert loaded is not None
    # next_due(anchor, 1h, _NOW) = _NOW + 30min; a due_at-based re-arm would be _NOW + 1h.
    assert loaded.due_at == _NOW + timedelta(minutes=30)
    assert loaded.anchor == anchor  # the grid origin persists across the fire


class _CancelRacingStore(InMemoryScheduleStore):
    """Scripts the cancel-during-fire race: the claim is handed out already stale."""

    async def claim_due(
        self, now: datetime, *, lease: timedelta, limit: int
    ) -> Sequence[ScheduleClaim]:
        claims = await super().claim_due(now, lease=lease, limit=limit)
        for claim in claims:
            await self.cancel(claim.item.id)
        return claims


async def test_a_fenced_off_finish_pushes_nothing() -> None:
    store = _CancelRacingStore()
    body = InMemoryBodyGateway(shown=True)
    await store.add(_item("r1"))
    await _ticker(store, body=body).run_once()
    assert body.notifications == ()  # cancel stuck; the dead fire delivered nothing


# --- tasks: the audited spawn dispatch ----------------------------------------------------------


async def test_task_fires_as_a_spawn_dispatch_and_records_the_outcome() -> None:
    store = InMemoryScheduleStore()
    spawn = FakeSpawnTool(content="[subagent 1] summarized")
    await store.add(_item("t1", kind=ScheduleKind.TASK, every=timedelta(hours=1), model="fast"))
    await _ticker(store, spawn=_dispatcher(spawn)).run_once()
    (call,) = spawn.calls
    assert call.arguments == {"instructions": [{"instruction": "text of t1", "model": "fast"}]}
    # The stamp carries the item's stored provenance (ADR-0027): clean, and attributed to
    # the chat that scheduled it.
    assert call.stamp == TurnStamp(session_id="chat-1", tainted=False)
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.last_outcome == "[subagent 1] summarized"
    assert loaded.due_at == _NOW + timedelta(hours=1)


async def test_tainted_task_rides_the_dispatcher_stamp() -> None:
    store = InMemoryScheduleStore()
    spawn = FakeSpawnTool()
    await store.add(_item("t1", kind=ScheduleKind.TASK, every=timedelta(hours=1), tainted=True))
    await _ticker(store, spawn=_dispatcher(spawn)).run_once()
    (call,) = spawn.calls
    assert call.stamp.tainted is True  # -> SubagentTask.tainted -> ADR-0017 pinning


async def test_untrusted_task_result_taints_the_item() -> None:
    store = InMemoryScheduleStore()
    spawn = FakeSpawnTool(content="the file said hi", trust=Trust.UNTRUSTED)
    await store.add(_item("t1", kind=ScheduleKind.TASK, every=timedelta(hours=1)))
    await _ticker(store, spawn=_dispatcher(spawn)).run_once()
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.tainted is True  # fire-time taint OR'd on; the listing now fences it


async def test_task_error_result_is_a_failed_outcome() -> None:
    store = InMemoryScheduleStore()
    spawn = FakeSpawnTool(content="bad instructions", is_error=True)
    await store.add(_item("t1", kind=ScheduleKind.TASK, every=timedelta(hours=1)))
    await _ticker(store, spawn=_dispatcher(spawn)).run_once()
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.last_outcome == "FAILED: bad instructions"


async def test_task_store_failure_is_a_failed_outcome() -> None:
    store = InMemoryScheduleStore()
    spawn = FakeSpawnTool(raise_task_store=True)
    await store.add(_item("t1", kind=ScheduleKind.TASK, every=timedelta(hours=1)))
    await _ticker(store, spawn=_dispatcher(spawn)).run_once()
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.last_outcome is not None
    assert "FAILED: the task store is unavailable" in loaded.last_outcome


async def test_task_without_delegation_wired_fails_cleanly() -> None:
    # A durable TASK outliving a reconfig: an ok=False outcome, not a crash or lease cycle.
    store = InMemoryScheduleStore()
    await store.add(_item("t1", kind=ScheduleKind.TASK, every=timedelta(hours=1)))
    await _ticker(store).run_once()
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.last_outcome == "FAILED: subagent delegation is not wired"
    assert loaded.due_at == _NOW + timedelta(hours=1)  # recurring: re-armed, not cycling


async def test_one_shot_task_is_cleaned_up_after_its_fire() -> None:
    store = InMemoryScheduleStore()
    spawn = FakeSpawnTool()
    await store.add(_item("t1", kind=ScheduleKind.TASK))
    await _ticker(store, spawn=_dispatcher(spawn)).run_once()
    assert await store.get("t1") is None  # terminal cleanup (outcome history is deferred)


async def test_a_hung_fire_is_cancelled_at_the_lease_and_released() -> None:
    """One wedged task cannot stall scheduling: wait_for cancels it, the claim releases."""

    class HangingSpawnTool(FakeSpawnTool):
        async def invoke(self, call: ToolCall) -> ToolResult:
            del call
            await asyncio.Event().wait()  # a wedged inference socket, forever
            msg = "unreachable"
            raise AssertionError(msg)

    store = InMemoryScheduleStore()
    await store.add(_item("t1", kind=ScheduleKind.TASK, every=timedelta(hours=1)))
    settings = TickerSettings(poll_s=0.001, lease=timedelta(milliseconds=50), claim_limit=8)
    ticker = ScheduleTicker(store, FixedClock(), settings, spawn=_dispatcher(HangingSpawnTool()))
    await asyncio.wait_for(ticker.run_once(), timeout=2.0)  # bounded, not stalled
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.status.value == "pending"  # released: the next pass re-fires it


async def test_a_gated_spawn_is_hard_denied_on_the_autonomous_path() -> None:
    """CORTEX_TOOLS_GATED covers the ticker too: no confirmer exists, so the fire denies."""
    store = InMemoryScheduleStore()
    spawn = FakeSpawnTool()
    gated = ToolDispatcher(
        CompositeToolRegistry([spawn]),
        RecordingAuditSink(),
        FixedClock(),
        gated_names={"spawn_subagents"},
    )
    await store.add(_item("t1", kind=ScheduleKind.TASK, every=timedelta(hours=1)))
    await _ticker(store, spawn=gated).run_once()
    assert spawn.calls == []  # never invoked, since the gate blocked it before the tool
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.last_outcome is not None
    assert loaded.last_outcome.startswith("FAILED: ")


# --- pass robustness ----------------------------------------------------------------------------


class _FinishFailsStore(InMemoryScheduleStore):
    """finish raises (store down mid-fire); release is recorded to prove the pass cleans up."""

    def __init__(self) -> None:
        super().__init__()
        self.released: list[str] = []
        self.release_fails = False

    async def finish(self, claim: ScheduleClaim, outcome: FireOutcome) -> bool:
        del outcome
        msg = f"finish of {claim.item.id} failed"
        raise ScheduleStoreError(msg)

    async def release(self, claim: ScheduleClaim) -> bool:
        if self.release_fails:
            msg = "release failed"
            raise ScheduleStoreError(msg)
        self.released.append(claim.item.id)
        return await super().release(claim)


async def test_a_failing_fire_releases_its_claim() -> None:
    store = _FinishFailsStore()
    await store.add(_item("r1"))
    await _ticker(store).run_once()
    assert store.released == ["r1"]
    loaded = await store.get("r1")
    assert loaded is not None  # back to PENDING: the next pass retries


async def test_a_failing_release_is_left_to_the_lease() -> None:
    store = _FinishFailsStore()
    store.release_fails = True
    await store.add(_item("r1"))
    await _ticker(store).run_once()  # logs; must not raise, since the lease recovers the claim


class _FlakyClaimStore(InMemoryScheduleStore):
    """The first claim_due raises (store down for one pass); later passes work."""

    def __init__(self) -> None:
        super().__init__()
        self.attempts = 0
        self.fired = asyncio.Event()

    async def claim_due(
        self, now: datetime, *, lease: timedelta, limit: int
    ) -> Sequence[ScheduleClaim]:
        self.attempts += 1
        if self.attempts == 1:
            msg = "redis down"
            raise ScheduleStoreError(msg)
        return await super().claim_due(now, lease=lease, limit=limit)

    async def finish(self, claim: ScheduleClaim, outcome: FireOutcome) -> bool:
        finished = await super().finish(claim, outcome)
        if finished:
            self.fired.set()
        return finished


async def test_run_survives_a_failing_pass_and_stops_on_signal() -> None:
    store = _FlakyClaimStore()
    await store.add(_item("r1"))
    ticker = _ticker(store)
    task = asyncio.create_task(ticker.run())
    await asyncio.wait_for(store.fired.wait(), timeout=1.0)  # pass 1 failed; pass 2 fired
    ticker.stop()
    await asyncio.wait_for(task, timeout=1.0)
    assert store.attempts >= 2


async def test_stop_before_any_pass_ends_the_loop_immediately() -> None:
    ticker = _ticker(InMemoryScheduleStore())
    ticker.stop()
    await asyncio.wait_for(ticker.run(), timeout=1.0)
