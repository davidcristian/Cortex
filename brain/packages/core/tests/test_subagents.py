"""Behavior tests for the subagent value types (ADR-0010)."""

from datetime import UTC, datetime

import pytest

from cortex_core import SubagentResult, SubagentTask

_AT = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)


def test_task_requires_timezone_aware_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        SubagentTask(id="t1", instruction="do", context="", at=datetime(2026, 7, 3, 12, 0))  # noqa: DTZ001


def test_task_holds_its_fields() -> None:
    task = SubagentTask(id="t1", instruction="do", context="ctx", at=_AT)
    assert (task.id, task.instruction, task.context, task.at) == ("t1", "do", "ctx", _AT)


def test_result_defaults_to_a_success_with_no_detail() -> None:
    result = SubagentResult(task_id="t1", output="done")
    assert (result.ok, result.detail) == (True, "")


def test_result_can_carry_a_failure_and_its_reason() -> None:
    result = SubagentResult(task_id="t1", output="", ok=False, detail="boom")
    assert (result.ok, result.detail) == (False, "boom")
