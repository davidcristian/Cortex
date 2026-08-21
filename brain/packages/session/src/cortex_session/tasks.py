"""RedisTaskStore: the TaskStore port over Redis keys for subagent tasks + results (ADR-0010).

Key layout: ``cortex:task:{id}`` holds the ``SubagentTask``, ``cortex:task:{id}:result`` the
``SubagentResult``. Each is one JSON document with an ISO-8601 timestamp, written with a short TTL
because task state is *hot and ephemeral*: it lives only for the in-flight delegation. Unlike the
durable session history (and its schema-version escape hatch), a task is written and read back by
one deployment within one turn, so it carries no ``v``/``kind`` markers. Redis is the state a
subagent is a stateless function over. It survives an orchestrator restart or a model swap
mid-delegation (the one hard rule). This adapter only translates: every backend failure crosses
the port as ``TaskStoreError`` with the cause chained, and a corrupt record fails LOUDLY. The
whole record round-trips, including ``model``/``tainted`` on a task and ``tainted`` on a result
(ADR-0018): taint that did not survive a re-read would fail open. The task's ``session_id`` and
``turn_id`` round-trip for the neighbouring reason (ADR-0009 named-work addendum): the runner
audits a delegated call under the turn that spawned it, and an attribution lost in the store
would make the trail claim the work belonged to nobody.
"""

import json
from datetime import datetime
from typing import Any, cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

from cortex_core import SubagentResult, SubagentTask, TaskStoreError
from cortex_session.store import DEFAULT_REDIS_URL

# Task state is short-lived (a delegation completes within a turn); expire keys so none leak.
_TASK_TTL_SECONDS = 3600


def _task_key(task_id: str) -> str:
    return f"cortex:task:{task_id}"


def _result_key(task_id: str) -> str:
    return f"cortex:task:{task_id}:result"


def _encode_task(task: SubagentTask) -> str:
    return json.dumps(
        {
            "id": task.id,
            "instruction": task.instruction,
            "context": task.context,
            "at": task.at.isoformat(),
            "model": task.model,
            "tainted": task.tainted,
            "session_id": task.session_id,
            "turn_id": task.turn_id,
        }
    )


def _decode_task(raw: bytes | str, task_id: str) -> SubagentTask:
    try:
        fields = cast("dict[str, Any]", json.loads(raw))
        return SubagentTask(
            id=fields["id"],
            instruction=fields["instruction"],
            context=fields["context"],
            at=datetime.fromisoformat(fields["at"]),
            model=fields["model"],
            tainted=fields["tainted"],
            session_id=fields["session_id"],
            turn_id=fields["turn_id"],
        )
    except (KeyError, TypeError, ValueError) as err:
        msg = f"corrupt task record at {_task_key(task_id)!r}"
        raise TaskStoreError(msg) from err


def _encode_result(result: SubagentResult) -> str:
    return json.dumps(
        {
            "task_id": result.task_id,
            "output": result.output,
            "ok": result.ok,
            "detail": result.detail,
            "tainted": result.tainted,
        }
    )


def _decode_result(raw: bytes | str, task_id: str) -> SubagentResult:
    try:
        fields = cast("dict[str, Any]", json.loads(raw))
        return SubagentResult(
            task_id=fields["task_id"],
            output=fields["output"],
            ok=fields["ok"],
            detail=fields["detail"],
            tainted=fields["tainted"],
        )
    except (KeyError, TypeError, ValueError) as err:
        msg = f"corrupt result record at {_result_key(task_id)!r}"
        raise TaskStoreError(msg) from err


class RedisTaskStore:
    """TaskStore adapter over redis-py asyncio (injected client or ``from_url``)."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    @classmethod
    def from_url(cls, url: str = DEFAULT_REDIS_URL) -> "RedisTaskStore":
        """Build a store owning a client for ``url``; close it via ``aclose()``."""
        return cls(Redis.from_url(url))  # pyright: ignore[reportUnknownMemberType]

    async def aclose(self) -> None:
        """Release the client's connections (call at composition-root shutdown)."""
        try:
            await self._client.aclose()
        except RedisError as err:
            msg = "closing the Redis client failed"
            raise TaskStoreError(msg) from err

    async def put_task(self, task: SubagentTask) -> None:
        """Persist one delegated task under a short TTL."""
        try:
            await self._client.set(_task_key(task.id), _encode_task(task), ex=_TASK_TTL_SECONDS)
        except RedisError as err:
            msg = f"put_task for {task.id!r} failed"
            raise TaskStoreError(msg) from err

    async def get_task(self, task_id: str) -> SubagentTask | None:
        """Return the task with ``task_id``, or None when unknown/expired."""
        try:
            raw = await self._client.get(_task_key(task_id))
        except RedisError as err:
            msg = f"get_task for {task_id!r} failed"
            raise TaskStoreError(msg) from err
        return _decode_task(raw, task_id) if raw is not None else None

    async def put_result(self, result: SubagentResult) -> None:
        """Persist one subagent result under a short TTL."""
        try:
            key = _result_key(result.task_id)
            await self._client.set(key, _encode_result(result), ex=_TASK_TTL_SECONDS)
        except RedisError as err:
            msg = f"put_result for {result.task_id!r} failed"
            raise TaskStoreError(msg) from err

    async def get_result(self, task_id: str) -> SubagentResult | None:
        """Return the result for ``task_id``, or None until the subagent has finished."""
        try:
            raw = await self._client.get(_result_key(task_id))
        except RedisError as err:
            msg = f"get_result for {task_id!r} failed"
            raise TaskStoreError(msg) from err
        return _decode_result(raw, task_id) if raw is not None else None
