"""Shared TaskStore behavior checks. Every implementation must pass all of them.

Driven by the parametrized contract test (in-memory fake + fakeredis-backed Redis adapter).
The two must be observably interchangeable behind the port (ports-before-adapters, ADR-0010).
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

from cortex_core import SubagentResult, SubagentTask, TaskStore

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


def _task_id() -> str:
    return f"contract-{uuid4()}"


def make_task(
    task_id: str,
    *,
    instruction: str = "do it",
    context: str = "",
    model: str = "",
    tainted: bool = False,
) -> SubagentTask:
    return SubagentTask(
        id=task_id, instruction=instruction, context=context, at=_AT, model=model, tainted=tainted
    )


async def check_missing_task_and_result_are_none(store: TaskStore) -> None:
    """An unknown id reads back as None from both getters, not an error."""
    task_id = _task_id()
    assert await store.get_task(task_id) is None
    assert await store.get_result(task_id) is None


async def check_task_round_trips(store: TaskStore) -> None:
    """A stored task reads back field-for-field, the resolution inputs included (ADR-0018).

    The spawning dispatch's attribution is on that record too (ADR-0009 named-work and fired-work
    addenda), and it has to survive the round trip for the same reason the taint does: the runner
    reads the task back to learn whose work it is doing, so an attribution lost in the store would
    file a delegated call in the audit trail under no work identity at all. All three identities
    are set here even though no single spawn carries all three, because the codec must not drop a
    field it was handed, and a fixture that left one empty could not distinguish a dropped field
    from a field that was never set.
    """
    task = replace(
        make_task(
            _task_id(),
            instruction="summarize the notes",
            context="notes: ...",
            model="fast",
            tainted=True,
        ),
        session_id="chat-7",
        turn_id="t-7",
        item_id="r-7",
    )
    await store.put_task(task)
    assert await store.get_task(task.id) == task


async def check_result_round_trips(store: TaskStore) -> None:
    """A stored result reads back field-for-field, failures and taint included.

    Taint has to survive the round trip (ADR-0018): a result re-read after a restart that lost
    ``tainted`` would be treated as untainted, which is the gap a review of the subagent slice
    found and this check closes.
    """
    task_id = _task_id()
    ok = SubagentResult(task_id=task_id, output="done")
    await store.put_result(ok)
    assert await store.get_result(task_id) == ok
    failed = SubagentResult(task_id=task_id, output="", ok=False, detail="boom")
    await store.put_result(failed)  # overwrites
    assert await store.get_result(task_id) == failed
    tainted = SubagentResult(task_id=task_id, output="the file said hi", tainted=True)
    await store.put_result(tainted)
    assert await store.get_result(task_id) == tainted


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
