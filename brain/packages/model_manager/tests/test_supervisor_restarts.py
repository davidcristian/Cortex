import asyncio
import logging

import pytest
from model_host_contract import CORTEX, DEEP
from process_fakes import FakeChildProcesses, FakeProbe
from test_model_host_contract import contract_roster

from cortex_core import ModelHostState, PlainFormatter
from cortex_model_manager import (
    ModelStatus,
    ModelSupervisor,
    RestartBudget,
    RestartPolicy,
)
from cortex_model_manager.restarts import (
    DEFAULT_RESTART_DELAY_S,
    DEFAULT_RESTART_LIMIT,
    DEFAULT_STABLE_AFTER_S,
)

_TINY = 0.05


def _supervisor(
    processes: FakeChildProcesses | None = None,
    *,
    limit: int = 3,
    now: list[float] | None = None,
) -> tuple[ModelSupervisor, FakeChildProcesses]:
    children = processes or FakeChildProcesses()
    clock = now if now is not None else [0.0]
    supervisor = ModelSupervisor(
        contract_roster(),
        children,
        FakeProbe(),
        stop_grace_s=_TINY,
        reap_timeout_s=_TINY,
        restarts=RestartBudget(
            RestartPolicy(models=(CORTEX,), limit=limit, delay_s=0.0), lambda: clock[0]
        ),
    )
    return supervisor, children


async def _settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


def test_the_shipped_policy_covers_nothing_and_allows_three_restarts() -> None:
    policy = RestartPolicy()
    assert tuple(policy.models) == ()
    assert policy.limit == DEFAULT_RESTART_LIMIT == 3
    assert policy.delay_s == DEFAULT_RESTART_DELAY_S
    assert policy.stable_after_s == DEFAULT_STABLE_AFTER_S
    budget = RestartBudget(RestartPolicy(models=(CORTEX,)), lambda: 0.0)
    assert budget.covers(CORTEX)
    assert not budget.covers(DEEP)


async def test_a_covered_model_that_exits_unasked_is_started_again(
    caplog: pytest.LogCaptureFixture,
) -> None:
    supervisor, processes = _supervisor()
    await supervisor.start(CORTEX)
    first = processes.spawned[0]
    with caplog.at_level(logging.WARNING):
        first.exit(-9)
        await _settle()
    second = processes.spawned[1]
    assert second.argv == first.argv
    assert await supervisor.status(CORTEX) == ModelStatus(
        CORTEX, ModelHostState.LOADING, f"pid {second.pid} is not serving yet"
    )
    assert [PlainFormatter().format(record) for record in caplog.records] == [
        "WARNING:cortex_model_manager.supervisor:a model process exited without being asked to; "
        f"starting it again attempt=1 code=-9 model={CORTEX} pid={first.pid}"
    ]


async def test_a_model_the_policy_does_not_cover_stays_failed() -> None:
    supervisor, processes = _supervisor()
    await supervisor.start(DEEP)
    processes.spawned[0].exit(1)
    await _settle()
    assert len(processes.spawned) == 1
    assert (await supervisor.status(DEEP)).state is ModelHostState.FAILED


async def test_a_stop_that_was_asked_for_is_never_undone() -> None:
    supervisor, processes = _supervisor()
    await supervisor.start(CORTEX)
    await supervisor.stop(CORTEX)
    await _settle()
    assert len(processes.spawned) == 1
    assert (await supervisor.status(CORTEX)).state is ModelHostState.STOPPED


async def test_a_start_that_already_replaced_the_exited_process_is_not_doubled() -> None:
    supervisor, processes = _supervisor()
    await supervisor.start(CORTEX)
    processes.spawned[0].exit(1)
    await supervisor.start(CORTEX)
    await _settle()
    assert len(processes.spawned) == 2


async def test_the_budget_runs_out_and_the_model_stays_failed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    supervisor, processes = _supervisor(limit=2)
    await supervisor.start(CORTEX)
    for child in range(3):
        processes.spawned[child].exit(1)
        await _settle()
    assert len(processes.spawned) == 3
    assert await supervisor.status(CORTEX) == ModelStatus(
        CORTEX, ModelHostState.FAILED, "the process exited with code 1"
    )
    assert caplog.records[-1].levelno == logging.ERROR
    assert caplog.records[-1].message == (
        "a model process keeps exiting, so it stays failed until a start is asked for"
    )


async def test_a_process_that_ran_stably_gets_the_whole_budget_back() -> None:
    now = [0.0]
    supervisor, processes = _supervisor(limit=1, now=now)
    await supervisor.start(CORTEX)
    processes.spawned[0].exit(1)
    await _settle()
    now[0] = DEFAULT_STABLE_AFTER_S
    processes.spawned[1].exit(1)
    await _settle()
    assert len(processes.spawned) == 3
    now[0] = DEFAULT_STABLE_AFTER_S * 2 - 1
    processes.spawned[2].exit(1)
    await _settle()
    assert len(processes.spawned) == 3


async def test_an_explicit_start_gives_the_budget_back() -> None:
    supervisor, processes = _supervisor(limit=1)
    await supervisor.start(CORTEX)
    processes.spawned[0].exit(1)
    await _settle()
    await supervisor.start(CORTEX)
    processes.spawned[1].exit(1)
    await _settle()
    assert len(processes.spawned) == 3


async def test_a_restart_whose_spawn_fails_leaves_the_exit_on_record(
    caplog: pytest.LogCaptureFixture,
) -> None:
    supervisor, processes = _supervisor()
    await supervisor.start(CORTEX)
    processes.error = OSError("no such file or directory")
    with caplog.at_level(logging.ERROR):
        processes.spawned[0].exit(7)
        await _settle()
    assert "a model process could not be started again" in caplog.text
    assert await supervisor.status(CORTEX) == ModelStatus(
        CORTEX, ModelHostState.FAILED, "the process exited with code 7"
    )


async def test_stop_all_ends_a_watch_whose_process_never_exits() -> None:
    supervisor, processes = _supervisor(FakeChildProcesses(exits_on=None))
    await supervisor.start(CORTEX)
    await supervisor.stop_all()
    await _settle()
    assert asyncio.all_tasks() == {asyncio.current_task()}
    assert len(processes.spawned) == 1
