"""Schedule wiring: the store, the built-ins, the ticker, and its lifecycle."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta

from cortex_core import (
    BodyGateway,
    BuiltinTool,
    CancelScheduledTool,
    Clock,
    CompositeToolRegistry,
    EditScheduledTool,
    ListScheduledTool,
    ScheduleStore,
    ScheduleTaskTool,
    SnoozeScheduledTool,
    SpawnSubagentsTool,
    ToolDispatcher,
    ZoneContext,
)
from cortex_orchestrator.builders import noop_aclose
from cortex_orchestrator.config_schedule import ScheduleConfig
from cortex_orchestrator.dispatch_builders import DEFAULT_DISPATCH_SETUP, DispatchSetup
from cortex_orchestrator.ticker import ScheduleTicker, TickerSettings
from cortex_session import ZONEINFO_RESOLVER, RedisScheduleStore

TICKER_STOP_GRACE_S = 5.0

_logger = logging.getLogger(__name__)


def build_schedule(
    config: ScheduleConfig,
    redis_url: str,
    *,
    store_factory: Callable[[str], RedisScheduleStore] = RedisScheduleStore.from_url,
) -> tuple[ScheduleStore | None, Callable[[], Awaitable[None]]]:
    """The durable ScheduleStore, or None when scheduling is disabled (the default)."""
    if config.backend != "redis":
        return None, noop_aclose
    store = store_factory(redis_url)
    return store, store.aclose


def build_schedule_tools(
    config: ScheduleConfig,
    schedules: ScheduleStore | None,
    clock: Clock,
    *,
    tasks_enabled: bool,
) -> list[BuiltinTool]:
    """The five cortex-only built-ins, or nothing when scheduling is off."""
    if schedules is None:
        return []
    zone = config.display_zone()
    zones = ZoneContext(default=zone, resolver=ZONEINFO_RESOLVER)
    return [
        ScheduleTaskTool(
            schedules,
            clock,
            tasks_enabled=tasks_enabled,
            max_active=config.max_active,
            zones=zones,
        ),
        ListScheduledTool(schedules, zone=zone),
        CancelScheduledTool(schedules),
        SnoozeScheduledTool(schedules, clock, zone=zone),
        EditScheduledTool(schedules, clock, zones=zones),
    ]


def build_ticker(
    config: ScheduleConfig,
    schedules: ScheduleStore | None,
    clock: Clock,
    *,
    spawn_tool: SpawnSubagentsTool | None,
    body: BodyGateway | None,
    setup: DispatchSetup = DEFAULT_DISPATCH_SETUP,
) -> ScheduleTicker | None:
    """The firing loop over the store, or None when scheduling is off."""
    if schedules is None:
        return None
    spawn = (
        ToolDispatcher(
            CompositeToolRegistry([spawn_tool]),
            setup.audit,
            clock,
            policy=setup.policy,
        )
        if spawn_tool is not None
        else None
    )
    settings = TickerSettings(
        poll_s=config.poll_s,
        lease=timedelta(seconds=config.lease_s),
        claim_limit=config.claim_limit,
        # The same zone the rendering built-ins get: a calendar item's next fire is wall-clock
        # arithmetic, so creating and firing must read one zone or a rule fires somewhere other
        # than where it was scheduled.
        zone=config.display_zone(),
    )
    return ScheduleTicker(schedules, clock, settings, spawn=spawn, body=body)


def start_ticker(ticker: ScheduleTicker | None) -> "asyncio.Task[None] | None":
    """Start the loop beside ``serve`` (the pump-task discipline); None stays None."""
    if ticker is None:
        return None
    task = asyncio.create_task(ticker.run(), name="schedule-ticker")
    task.add_done_callback(_log_ticker_death)
    return task


def _log_ticker_death(task: "asyncio.Task[None]") -> None:
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        _logger.error("the schedule ticker died unexpectedly", exc_info=error)


async def stop_ticker(
    ticker: ScheduleTicker | None,
    task: "asyncio.Task[None] | None",
    *,
    grace_s: float = TICKER_STOP_GRACE_S,
) -> None:
    """Graceful stop: signal, wait out the in-flight pass, force-cancel past the grace."""
    if ticker is None or task is None:
        return
    ticker.stop()
    try:
        await asyncio.wait_for(task, timeout=grace_s)
    except TimeoutError:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
