"""The schedule builders + the ticker lifecycle (ADR-0025 decision 7)."""

import asyncio
from datetime import UTC, datetime, timedelta

from fakeredis import FakeAsyncRedis, FakeServer

from cortex_core import (
    CalendarRule,
    EchoInferenceBackend,
    InMemoryBodyGateway,
    InMemoryScheduleStore,
    InMemoryTaskStore,
    PlacementRequest,
    PlacementTarget,
    ResourceBudgetScheduler,
    ScheduledItem,
    ScheduleKind,
    SpawnSubagentsTool,
    SubagentProfile,
    SubagentResources,
    SubagentRoster,
    SubagentRunner,
    SystemClock,
    ToolCall,
    VramBudgetPlacer,
)
from cortex_orchestrator import (
    ScheduleConfig,
    ScheduleTicker,
    TickerSettings,
    build_builtin_tools,
    build_schedule,
    build_schedule_tools,
    build_ticker,
    start_ticker,
    stop_ticker,
)
from cortex_orchestrator.schedule_builders import (
    _log_ticker_death,  # pyright: ignore[reportPrivateUsage] - the supervision hook under test
)
from cortex_session import RedisScheduleStore

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return _NOW


def _spawn_tool() -> SpawnSubagentsTool:
    # A real spawn tool over fakes: build_ticker only needs its identity, not a run.
    backend = EchoInferenceBackend()
    resources = SubagentResources(
        backends={PlacementTarget.GPU: backend, PlacementTarget.CPU: backend},
        scheduler=ResourceBudgetScheduler(4.0, 8.0),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=12.0),
        request=PlacementRequest("subagent", 1.0, 1.0, 1.0),
    )
    roster = SubagentRoster(
        entries={"subagent": SubagentProfile(resources=resources)}, default="subagent"
    )
    store = InMemoryTaskStore()
    runner = SubagentRunner(store, roster, FixedClock())
    return SpawnSubagentsTool(runner, store, FixedClock())


def test_build_schedule_defaults_to_disabled() -> None:
    store, _close = build_schedule(ScheduleConfig(backend="none"), "redis://ignored")
    assert store is None


async def test_build_schedule_redis_builds_and_closes_the_store() -> None:
    urls: list[str] = []

    def factory(url: str) -> RedisScheduleStore:
        urls.append(url)
        return RedisScheduleStore(FakeAsyncRedis(server=FakeServer()))

    store, close = build_schedule(
        ScheduleConfig(backend="redis"), "redis://redis:6379/0", store_factory=factory
    )
    assert isinstance(store, RedisScheduleStore)
    assert urls == ["redis://redis:6379/0"]
    await close()  # the store's aclose: releases the client


def test_build_schedule_tools_off_when_scheduling_is_off() -> None:
    assert build_schedule_tools(ScheduleConfig(), None, FixedClock(), tasks_enabled=True) == []


def test_build_schedule_tools_names_and_honest_advertisement() -> None:
    tools = build_schedule_tools(
        ScheduleConfig(max_active=5), InMemoryScheduleStore(), FixedClock(), tasks_enabled=False
    )
    specs = {tool.spec.name: tool.spec for tool in tools}
    assert set(specs) == {
        "schedule_task",
        "list_scheduled",
        "cancel_scheduled",
        "snooze_scheduled",
        "edit_scheduled",
    }
    # tasks_enabled=False: the spec offers reminders only (the fire path still answers a
    # stale TASK with an ok=False outcome via the ticker's no-runner branch).
    assert dict(specs["schedule_task"].parameters["properties"])["kind"]["enum"] == ["reminder"]


def test_build_builtin_tools_composes_in_capability_order() -> None:
    spawn = _spawn_tool()
    body = InMemoryBodyGateway()
    schedule = build_schedule_tools(
        ScheduleConfig(), InMemoryScheduleStore(), FixedClock(), tasks_enabled=True
    )
    names = [tool.spec.name for tool in build_builtin_tools(spawn, body, schedule)]
    assert names == [
        "spawn_subagents",
        "get_volume",
        "set_volume",
        "schedule_task",
        "list_scheduled",
        "cancel_scheduled",
        "snooze_scheduled",
        "edit_scheduled",
    ]
    assert build_builtin_tools(None, None) == []


def test_build_ticker_off_when_scheduling_is_off() -> None:
    ticker = build_ticker(ScheduleConfig(), None, FixedClock(), spawn_tool=_spawn_tool(), body=None)
    assert ticker is None


def test_build_ticker_wires_the_loop() -> None:
    ticker = build_ticker(
        ScheduleConfig(backend="redis"),
        InMemoryScheduleStore(),
        FixedClock(),
        spawn_tool=_spawn_tool(),
        body=InMemoryBodyGateway(),
    )
    assert isinstance(ticker, ScheduleTicker)
    without_spawn = build_ticker(
        ScheduleConfig(backend="redis"),
        InMemoryScheduleStore(),
        FixedClock(),
        spawn_tool=None,
        body=None,
    )
    assert isinstance(without_spawn, ScheduleTicker)


async def test_start_and_stop_ticker_lifecycle() -> None:
    assert start_ticker(None) is None
    await stop_ticker(None, None)  # both no-ops must be clean
    ticker = ScheduleTicker(
        InMemoryScheduleStore(),
        SystemClock(),
        TickerSettings(poll_s=0.001, lease=timedelta(minutes=5), claim_limit=8),
    )
    task = start_ticker(ticker)
    assert task is not None
    await asyncio.sleep(0.005)  # let a pass or two run
    await stop_ticker(ticker, task)
    assert task.done()


async def test_stop_ticker_forces_a_cancel_past_the_grace() -> None:
    class _StuckTicker(ScheduleTicker):
        async def run(self) -> None:
            await asyncio.Event().wait()  # never returns; ignores stop()

    ticker = _StuckTicker(
        InMemoryScheduleStore(),
        SystemClock(),
        TickerSettings(poll_s=0.001, lease=timedelta(minutes=5), claim_limit=8),
    )
    task = start_ticker(ticker)
    assert task is not None
    await stop_ticker(ticker, task, grace_s=0.01)
    assert task.cancelled()


async def test_log_ticker_death_covers_each_ending() -> None:
    async def boom() -> None:
        msg = "ticker bug"
        raise RuntimeError(msg)

    failed = asyncio.get_running_loop().create_task(boom())
    await asyncio.gather(failed, return_exceptions=True)
    _log_ticker_death(failed)  # logs the death (the supervision posture)

    async def forever() -> None:
        await asyncio.Event().wait()

    cancelled = asyncio.get_running_loop().create_task(forever())
    cancelled.cancel()
    await asyncio.gather(cancelled, return_exceptions=True)
    _log_ticker_death(cancelled)  # cancelled: not a death, nothing logged


async def test_the_configured_zone_reaches_every_rendering_builtin() -> None:
    """CORTEX_SCHEDULE_TZ is inert unless the builder threads it, so assert all three."""
    store = InMemoryScheduleStore()
    await store.add(
        ScheduledItem(
            id="item-1",
            kind=ScheduleKind.REMINDER,
            text="tea",
            session_id="",
            due_at=_NOW + timedelta(minutes=5),
            created_at=_NOW,
        )
    )
    tools = build_schedule_tools(
        ScheduleConfig(tz="Europe/Bucharest"), store, FixedClock(), tasks_enabled=True
    )
    specs = {tool.spec.name: tool.spec for tool in tools}
    invoke = {tool.spec.name: tool.invoke for tool in tools}
    assert "(Europe/Bucharest)" in specs["schedule_task"].description
    assert "due time (Europe/Bucharest)" in specs["list_scheduled"].description
    listed = await invoke["list_scheduled"](ToolCall(id="c1", name="list_scheduled", arguments={}))
    assert "due 2026-07-12T15:05:00+03:00" in listed.content
    snoozed = await invoke["snooze_scheduled"](
        ToolCall(id="c2", name="snooze_scheduled", arguments={"id": "item-1", "for_seconds": 3600})
    )
    assert "now due 2026-07-12T16:00:00+03:00" in snoozed.content


async def _rearm_of_a_nine_am_rule(config: ScheduleConfig) -> datetime:
    """Fire a 09:00 calendar reminder through a built ticker and report where it re-armed.

    Asserted through behavior rather than by reading the ticker's settings: the zone matters
    only because it moves the re-arm, so the re-arm is what the test should pin.
    """
    store = InMemoryScheduleStore()
    await store.add(
        ScheduledItem(
            id="cal-1",
            kind=ScheduleKind.REMINDER,
            text="stretch",
            session_id="",
            due_at=_NOW,
            created_at=_NOW,
            rule=CalendarRule(hour=9, minute=0),
        )
    )
    ticker = build_ticker(config, store, FixedClock(), spawn_tool=None, body=None)
    assert ticker is not None
    await ticker.run_once()
    (item,) = await store.list_active()
    return item.due_at


async def test_build_ticker_threads_the_configured_zone_into_its_settings() -> None:
    """Creating and firing must read one zone, or a rule fires somewhere it was not scheduled.

    ``build_schedule_tools`` already gave the rendering built-ins ``CORTEX_SCHEDULE_TZ``; the
    ticker needs the same value because a calendar re-arm is wall-clock arithmetic
    (ADR-0025 calendar addendum). _NOW is 12:00 UTC, so the next 09:00 in Bucharest (+03:00 in
    July) is the following morning at 06:00 UTC, three hours off the UTC reading.
    """
    config = ScheduleConfig(backend="redis", tz="Europe/Bucharest")
    assert await _rearm_of_a_nine_am_rule(config) == datetime(2026, 7, 13, 6, 0, tzinfo=UTC)


async def test_build_ticker_defaults_to_utc_like_the_built_ins() -> None:
    assert await _rearm_of_a_nine_am_rule(ScheduleConfig(backend="redis")) == datetime(
        2026, 7, 13, 9, 0, tzinfo=UTC
    )
