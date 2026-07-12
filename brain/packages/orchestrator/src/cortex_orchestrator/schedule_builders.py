"""Schedule wiring: the store, the built-ins, the ticker, and its lifecycle (ADR-0025).

Split from ``builders.py`` per the ``subagent_builders.py`` precedent; same contract of
builders called only by ``wiring.run_from_env``, each returning the dependency plus its
closer where one holds resources. Scheduling is disabled by default (``none``); with
``CORTEX_SCHEDULE_BACKEND=redis`` the durable store comes up at ``CORTEX_REDIS_URL``, the
four cortex-only built-ins join the composite set, and the ticker fires due items, sending
tasks through its own audited spawn dispatcher (``confirmer=None``, the fail-closed
autonomous posture), reminders to the deliverable slot plus a push attempt when the body
gateway is wired (no second knob).
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Collection
from datetime import timedelta

from cortex_core import (
    BodyGateway,
    BuiltinTool,
    CancelScheduledTool,
    Clock,
    CompositeToolRegistry,
    ListScheduledTool,
    ScheduleStore,
    ScheduleTaskTool,
    SnoozeScheduledTool,
    SpawnSubagentsTool,
    ToolDispatcher,
)
from cortex_orchestrator.builders import noop_aclose
from cortex_orchestrator.config_schedule import ScheduleConfig
from cortex_orchestrator.ticker import ScheduleTicker, TickerSettings
from cortex_session import RedisScheduleStore
from cortex_tools import LoggingAuditSink

# How long a graceful stop waits for the in-flight pass before the forced cancel; the
# store's claim lease recovers whatever a forced cancel interrupted.
TICKER_STOP_GRACE_S = 5.0

_logger = logging.getLogger(__name__)


def build_schedule(
    config: ScheduleConfig,
    redis_url: str,
    *,
    store_factory: Callable[[str], RedisScheduleStore] = RedisScheduleStore.from_url,
) -> tuple[ScheduleStore | None, Callable[[], Awaitable[None]]]:
    """The durable ScheduleStore, or None when scheduling is disabled (the default).

    ``store_factory`` exists so tests substitute a fakeredis-backed store; production
    always dials ``CORTEX_REDIS_URL``, which is the same append-only Redis the sessions trust.
    """
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
    """The four cortex-only built-ins, or nothing when scheduling is off (ADR-0025).

    ``tasks_enabled`` keys honest advertisement: without a spawn tool wired, the spec
    offers reminders only (and the fire path answers a stale TASK with an ok=False
    outcome should one outlive a reconfig).
    """
    if schedules is None:
        return []
    return [
        ScheduleTaskTool(
            schedules, clock, tasks_enabled=tasks_enabled, max_active=config.max_active
        ),
        ListScheduledTool(schedules),
        CancelScheduledTool(schedules),
        SnoozeScheduledTool(schedules, clock),
    ]


def build_ticker(
    config: ScheduleConfig,
    schedules: ScheduleStore | None,
    clock: Clock,
    *,
    spawn_tool: SpawnSubagentsTool | None,
    body: BodyGateway | None,
    gated_names: Collection[str] = (),
) -> ScheduleTicker | None:
    """The firing loop over the store, or None when scheduling is off.

    The ticker's TASK path is its own audited ``ToolDispatcher`` holding just the spawn
    tool: the fire gets an audit line, the dispatcher taint stamp (→ ADR-0017 pinning),
    and the fail-closed ``confirmer=None`` gate. All this leaves `build_subagents`' public shape
    untouched (ADR-0025 decision 4). ``gated_names`` is `CORTEX_TOOLS_GATED`, threaded so
    the user's backstop covers the autonomous path too (post-review hardening): a gated
    `spawn_subagents` hard-denies here (there is nobody to confirm), exactly the
    fail-closed answer the live turn's tainted branch gives. Push rides exactly when the
    body gateway is wired.
    """
    if schedules is None:
        return None
    spawn = (
        ToolDispatcher(
            CompositeToolRegistry([spawn_tool]),
            LoggingAuditSink(),
            clock,
            gated_names=gated_names,
        )
        if spawn_tool is not None
        else None
    )
    settings = TickerSettings(
        poll_s=config.poll_s,
        lease=timedelta(seconds=config.lease_s),
        claim_limit=config.claim_limit,
    )
    return ScheduleTicker(schedules, clock, settings, spawn=spawn, body=body)


def start_ticker(ticker: ScheduleTicker | None) -> "asyncio.Task[None] | None":
    """Start the loop beside ``serve`` (the pump-task discipline); None stays None.

    The done-callback logs an unexpected death as an error (the ADR-0025 supervision
    posture). With the loop's own pass guard it should never fire, which is the point.
    """
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
    """Graceful stop: signal, wait out the in-flight pass, force-cancel past the grace.

    The graceful path strands no claims (fires complete before the loop exits); a forced
    cancel leaves the store's lease to recover whatever was interrupted (ADR-0025 risks).
    """
    if ticker is None or task is None:
        return
    ticker.stop()
    try:
        await asyncio.wait_for(task, timeout=grace_s)
    except TimeoutError:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
