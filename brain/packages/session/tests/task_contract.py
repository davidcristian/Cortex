"""Shared TaskStore behavior checks. Every implementation must pass all of them.

Driven by the parametrized contract test (in-memory fake + fakeredis-backed Redis adapter).
The two must be observably interchangeable behind the port (ports-before-adapters, ADR-0010).
"""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

from cortex_core import SubagentResult, SubagentTask, TaskStore

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


def _task_id() -> str:
    return f"contract-{uuid4()}"


def make_task(task_id: str, *, instruction: str = "do it", context: str = "") -> SubagentTask:
    return SubagentTask(id=task_id, instruction=instruction, context=context, at=_AT)


async def check_missing_task_and_result_are_none(store: TaskStore) -> None:
    """An unknown id reads back as None from both getters, not an error."""
    task_id = _task_id()
    assert await store.get_task(task_id) is None
    assert await store.get_result(task_id) is None


async def check_task_round_trips(store: TaskStore) -> None:
    """A stored task reads back field-for-field."""
    task = make_task(_task_id(), instruction="summarize the notes", context="notes: ...")
    await store.put_task(task)
    assert await store.get_task(task.id) == task


async def check_result_round_trips(store: TaskStore) -> None:
    """A stored result reads back field-for-field, failures included."""
    task_id = _task_id()
    ok = SubagentResult(task_id=task_id, output="done")
    await store.put_result(ok)
    assert await store.get_result(task_id) == ok
    failed = SubagentResult(task_id=task_id, output="", ok=False, detail="boom")
    await store.put_result(failed)  # overwrites
    assert await store.get_result(task_id) == failed


async def check_task_timezone_fidelity(store: TaskStore) -> None:
    """A non-UTC timestamp survives the round-trip with its offset intact."""
    task_id = _task_id()
    at = datetime(2026, 7, 3, 17, 45, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    await store.put_task(SubagentTask(id=task_id, instruction="x", context="", at=at))
    loaded = await store.get_task(task_id)
    assert loaded is not None
    assert loaded.at.utcoffset() == timedelta(hours=5, minutes=30)


ALL_CHECKS = (
    check_missing_task_and_result_are_none,
    check_task_round_trips,
    check_result_round_trips,
    check_task_timezone_fidelity,
)
