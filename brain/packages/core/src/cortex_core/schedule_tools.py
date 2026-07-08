"""The ``schedule_task`` / ``list_scheduled`` / ``cancel_scheduled`` built-ins (ADR-0025).

Cortex-only by construction (built-ins never reach subagents, per ADR-0010/0013), so a subagent
cannot re-schedule: self-perpetuation is bounded exactly like depth-1 bounds delegation.
Ungated by default, as creating a schedule is reversible (``cancel_scheduled`` sticks, the store's
fenced protocol). Two creation bounds apply: the active-items cap, and the **tainted-task
refusal** (a turn that has read untrusted content cannot create a ``kind: "task"`` item at all;
an autonomous agent instruction authored by injected content is a standing directive, not a
reminder a human vets). The ``schedule_task`` spec is rebuilt per ``describe_tools`` walk and
carries the current UTC time from the injected ``Clock``. The model cannot otherwise compute an
absolute ``at``. Creation/cancel results are TRUSTED and never echo the stored text; the listing
does echo text, so it is TRUSTED only when every listed item is clean (the spawn aggregate rule, so
hostile text is fenced and re-taints the turn instead of laundering through a trusted result).
Bad arguments and a down store both become ``is_error`` results, never exceptions.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from cortex_core.errors import ScheduleStoreError
from cortex_core.ports import Clock, ScheduleStore
from cortex_core.schedule import ScheduledItem, ScheduleKind, ScheduleStatus
from cortex_core.schedule_args import MIN_EVERY_SECONDS, parse_schedule
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

SCHEDULE_TOOL_NAME = "schedule_task"
LIST_SCHEDULED_TOOL_NAME = "list_scheduled"
CANCEL_SCHEDULED_TOOL_NAME = "cancel_scheduled"

TAINTED_TASK_MSG = (
    "cannot schedule an autonomous task on a turn that has read untrusted external "
    "content; schedule a reminder instead, or re-ask in a fresh turn"
)
_STORE_DOWN = "the schedule store is unavailable"


def _uuid4_id() -> str:
    """Default item-id factory; injectable so tests can pin ids."""
    return str(uuid4())


def _store_down(call_id: str, err: ScheduleStoreError) -> ToolResult:
    return ToolResult(
        call_id=call_id, content=f"{_STORE_DOWN}: {err}", is_error=True, trust=Trust.TRUSTED
    )


def _error(call_id: str, message: str) -> ToolResult:
    return ToolResult(call_id=call_id, content=message, is_error=True, trust=Trust.TRUSTED)


def _utc(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds")


class ScheduleTaskTool:
    """Built-in ``schedule_task``: persist a reminder or autonomous task to fire later."""

    def __init__(
        self,
        store: ScheduleStore,
        clock: Clock,
        *,
        tasks_enabled: bool,
        max_active: int,
        item_id_factory: Callable[[], str] = _uuid4_id,
    ) -> None:
        self._store = store
        self._clock = clock
        self._tasks_enabled = tasks_enabled
        self._max_active = max_active
        self._item_id_factory = item_id_factory

    @property
    def spec(self) -> ToolSpec:
        """Rebuilt per walk: carries the current UTC time and is honest about task wiring."""
        what = "a reminder to deliver to the user"
        kinds = [ScheduleKind.REMINDER.value]
        properties: dict[str, Any] = {
            "kind": {"type": "string", "enum": kinds},
            "text": {
                "type": "string",
                "description": "The reminder text (or the task instruction).",
            },
            "at": {
                "type": "string",
                "description": (
                    "Absolute due time, ISO-8601 with a UTC offset, e.g. 2026-07-12T18:00:00+00:00."
                ),
            },
            "in_seconds": {
                "type": "number",
                "description": "Relative due time: seconds from now (alternative to 'at').",
            },
            "every_seconds": {
                "type": "number",
                "minimum": MIN_EVERY_SECONDS,
                "description": (
                    f"Repeat interval in seconds (min {MIN_EVERY_SECONDS}); omit for one-shot."
                ),
            },
        }
        if self._tasks_enabled:
            what = "a reminder to deliver to the user, or an autonomous task run by a subagent"
            kinds.append(ScheduleKind.TASK.value)
            properties["model"] = {
                "type": "string",
                "description": "Optional subagent roster name for a task; omit for the default.",
            }
        return ToolSpec(
            name=SCHEDULE_TOOL_NAME,
            description=(
                f"Schedule {what} for later; it fires even after a restart. "
                f"The current UTC date-time is {_utc(self._clock.now())}. "
                "Provide 'at' (ISO-8601 with offset) or 'in_seconds' (delay from now); "
                "add 'every_seconds' to recur."
            ),
            parameters={"type": "object", "properties": properties, "required": ["kind", "text"]},
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Validate, apply the creation bounds, persist, and confirm without echoing text.

        The tainted-task refusal is deterministic (the dispatcher's taint stamp on ``call``,
        never the model's claim): a tainted turn can schedule a reminder. Its text only ever
        reaches a human (badged) and never an autonomous task (ADR-0025 decision 3).
        """
        now = self._clock.now()
        parsed = parse_schedule(call.arguments, now=now, tasks_enabled=self._tasks_enabled)
        if isinstance(parsed, str):
            return _error(call.id, parsed)
        if parsed.kind is ScheduleKind.TASK and call.tainted:
            return _error(call.id, TAINTED_TASK_MSG)
        try:
            if len(await self._store.list_active()) >= self._max_active:
                return _error(
                    call.id,
                    f"the schedule is full ({self._max_active} active items); cancel one first",
                )
            item = ScheduledItem(
                id=self._item_id_factory(),
                kind=parsed.kind,
                text=parsed.text,
                session_id="",
                due_at=parsed.due_at,
                created_at=now,
                every=parsed.every,
                model=parsed.model,
                tainted=call.tainted,
            )
            await self._store.add(item)
        except ScheduleStoreError as err:
            return _store_down(call.id, err)
        recurring = (
            f", recurring every {int(parsed.every.total_seconds())}s" if parsed.every else ""
        )
        content = f"scheduled {parsed.kind.value} {item.id}: due {_utc(parsed.due_at)}{recurring}"
        return ToolResult(call_id=call.id, content=content, trust=Trust.TRUSTED)


def _describe(item: ScheduledItem) -> str:
    """One listing line per item; the stored text rides at the end, provenance marked."""
    recurring = f", every {int(item.every.total_seconds())}s" if item.every else ""
    fired = ", fired awaiting delivery" if item.deliverable_since is not None else ""
    firing = ", firing now" if item.status is ScheduleStatus.FIRING else ""
    tainted = ", from untrusted content" if item.tainted else ""
    marks = f"{recurring}{firing}{fired}{tainted}"
    line = f"[{item.id}] {item.kind.value} due {_utc(item.due_at)}{marks}: {item.text}"
    if item.last_outcome is not None:
        line += f"\n    last outcome: {item.last_outcome}"
    return line


class ListScheduledTool:
    """Built-in ``list_scheduled``: the active schedules, ids included for cancelling."""

    def __init__(self, store: ScheduleStore) -> None:
        self._store = store

    @property
    def spec(self) -> ToolSpec:
        """No arguments; lists ids, kinds, due times, recurrence, and status."""
        return ToolSpec(
            name=LIST_SCHEDULED_TOOL_NAME,
            description=(
                "List the active scheduled reminders and tasks: id, kind, due time (UTC), "
                "recurrence, and status. Use the id with cancel_scheduled."
            ),
            parameters={"type": "object", "properties": {}},
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """List active items; the listing is UNTRUSTED iff any item carries taint.

        A tainted item's text is attacker-influenced: fencing the whole listing (and
        re-tainting the turn) beats laundering it through a trusted result (ADR-0025).
        """
        try:
            items = await self._store.list_active()
        except ScheduleStoreError as err:
            return _store_down(call.id, err)
        if not items:
            return ToolResult(call_id=call.id, content="no scheduled items", trust=Trust.TRUSTED)
        trust = Trust.UNTRUSTED if any(item.tainted for item in items) else Trust.TRUSTED
        return ToolResult(
            call_id=call.id, content="\n".join(_describe(item) for item in items), trust=trust
        )


class CancelScheduledTool:
    """Built-in ``cancel_scheduled``: delete a schedule outright. It sticks mid-fire too."""

    def __init__(self, store: ScheduleStore) -> None:
        self._store = store

    @property
    def spec(self) -> ToolSpec:
        """Takes the id a listing (or creation confirmation) reported."""
        return ToolSpec(
            name=CANCEL_SCHEDULED_TOOL_NAME,
            description="Cancel a scheduled reminder or task by its id (see list_scheduled).",
            parameters={
                "type": "object",
                "properties": {"id": {"type": "string", "description": "The scheduled item's id."}},
                "required": ["id"],
            },
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Cancel by id; unknown ids are a correctable error, never an exception."""
        item_id = call.arguments.get("id")
        if not isinstance(item_id, str) or not item_id:
            return _error(call.id, "'id' must be a non-empty string")
        try:
            cancelled = await self._store.cancel(item_id)
        except ScheduleStoreError as err:
            return _store_down(call.id, err)
        if not cancelled:
            return _error(call.id, f"no scheduled item {item_id}")
        return ToolResult(call_id=call.id, content=f"cancelled {item_id}", trust=Trust.TRUSTED)
