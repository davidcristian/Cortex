"""Contract tests for the TaskStore port via its in-memory fake (ADR-0010).

The Redis adapter (Slice 7 CI half) must pass this same contract. The fake is its twin.
"""

from datetime import UTC, datetime

from cortex_core import InMemoryTaskStore, SubagentResult, SubagentTask

_AT = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)


async def test_put_and_get_task_round_trips() -> None:
    store = InMemoryTaskStore()
    task = SubagentTask(id="t1", instruction="do", context="", at=_AT)
    await store.put_task(task)
    assert await store.get_task("t1") == task


async def test_get_unknown_task_is_none() -> None:
    assert await InMemoryTaskStore().get_task("ghost") is None


async def test_put_and_get_result_round_trips() -> None:
    store = InMemoryTaskStore()
    result = SubagentResult(task_id="t1", output="done")
    await store.put_result(result)
    assert await store.get_result("t1") == result


async def test_get_unknown_result_is_none() -> None:
    assert await InMemoryTaskStore().get_result("ghost") is None
