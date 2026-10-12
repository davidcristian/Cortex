"""The ``schedule_task`` / ``list_scheduled`` built-ins."""

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from cortex_core.errors import ScheduleStoreError
from cortex_core.ports import Clock, ScheduleStore
from cortex_core.schedule import ScheduledItem, ScheduleKind
from cortex_core.schedule_args import MIN_EVERY_SECONDS, parse_schedule
from cortex_core.schedule_day_args import day_selector_properties, in_zone_property
from cortex_core.schedule_render import describe_item, effective_zone, recurrence_phrase
from cortex_core.schedule_time import UTC_DISPLAY, UTC_ZONE_CONTEXT, DisplayZone, ZoneContext
from cortex_core.schedule_verbs import error_result, store_down_result
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

SCHEDULE_TOOL_NAME = "schedule_task"
LIST_SCHEDULED_TOOL_NAME = "list_scheduled"

TAINTED_TASK_MSG = (
    "BLOCKED: this turn read untrusted external content, so no autonomous task can be "
    "scheduled in it, and this one was not scheduled. Tell the user it was not scheduled. A "
    "reminder (kind 'reminder') can still be scheduled in this turn, but only a successful "
    "call schedules one; do not say a reminder was set unless that call succeeded."
)


_NOT_ADDED = "it was on the schedule before this call, so no copy was added"


def _full_msg(max_active: int) -> str:
    """The result for a full schedule: nothing was stored, and only the user may free room."""
    return (
        f"NOT SCHEDULED: the schedule is full ({max_active} active items), so nothing was "
        "scheduled. Tell the user it was not scheduled because the schedule is full, and ask "
        "which item they want to cancel. Do not cancel any item yourself to make room."
    )


def _uuid4_id() -> str:
    """Default item-id factory; injectable so tests can use fixed ids."""
    return str(uuid4())


class ScheduleTaskTool:
    """Built-in ``schedule_task``: persist a reminder or autonomous task to fire later."""

    def __init__(
        self,
        store: ScheduleStore,
        clock: Clock,
        *,
        tasks_enabled: bool,
        max_active: int,
        zones: ZoneContext = UTC_ZONE_CONTEXT,
        item_id_factory: Callable[[], str] = _uuid4_id,
    ) -> None:
        self._store = store
        self._clock = clock
        self._tasks_enabled = tasks_enabled
        self._max_active = max_active
        self._zone = zones.default
        self._resolve_zone = zones.resolver
        self._item_id_factory = item_id_factory

    @property
    def spec(self) -> ToolSpec:
        """Rebuilt per walk: it states the current local time and matches the task wiring."""
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
                    "One-time due time, an ISO-8601 date-time, e.g. 2026-07-12T18:00:00. Use "
                    "this for a single time such as 'tomorrow at 10:00'. An explicit offset is "
                    f"honored; without one it is read as {self._zone.name} local time."
                ),
            },
            "in_seconds": {
                "type": "number",
                "description": "Relative due time: seconds from now (alternative to 'at').",
            },
            "every_seconds": {
                "type": "number",
                "minimum": 0,
                "description": (
                    f"Repeat interval in seconds (min {MIN_EVERY_SECONDS}); 0 or omitted for "
                    "a one-shot."
                ),
            },
            "at_time": {
                "type": "string",
                "description": (
                    "Makes the item repeat: a 24-hour HH:MM wall-clock time in "
                    f"{self._zone.name} (or in 'in_zone'), e.g. 09:00, fired every day, or only "
                    "on the days 'on_days', 'on_month_days' or 'on_dates' select. Use it only "
                    "when the user asks for a repeat, such as 'every day at 9'; for one time, "
                    "such as 'tomorrow at 10:00', use 'at' instead. It keeps the same clock "
                    "time across daylight saving. Alternative to 'at'/'in_seconds'."
                ),
            },
            **day_selector_properties(),
            **in_zone_property(),
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
                f"The current date-time is {self._zone.render(self._clock.now())} "
                f"({self._zone.name}). "
                "For one time, provide 'at' (ISO-8601 date-time) or 'in_seconds' (delay "
                "from now), and add 'every_seconds' only to repeat at a fixed interval. To "
                "repeat at a wall-clock time, provide 'at_time' (HH:MM) with optional "
                "'on_days', 'on_month_days', 'on_dates', or 'in_zone'; 'at_time' alone "
                "repeats every day."
            ),
            parameters={"type": "object", "properties": properties, "required": ["kind", "text"]},
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Validate, apply the creation bounds, persist, and confirm without echoing text."""
        now = self._clock.now()
        parsed = parse_schedule(
            call.arguments,
            now=now,
            tasks_enabled=self._tasks_enabled,
            zone=self._zone,
            resolve_zone=self._resolve_zone,
        )
        if isinstance(parsed, str):
            return error_result(call.id, parsed)
        if parsed.kind is ScheduleKind.TASK and call.stamp.tainted:
            return error_result(call.id, TAINTED_TASK_MSG)
        item = ScheduledItem(
            id=self._item_id_factory(),
            kind=parsed.kind,
            text=parsed.text,
            session_id=call.stamp.session_id,
            due_at=parsed.due_at,
            created_at=now,
            every=parsed.every,
            rule=parsed.rule,
            model=parsed.model,
            tainted=call.stamp.tainted,
        )
        try:
            active = await self._store.list_active()
            held = next((each for each in active if _same_request(each, item)), None)
            if held is None:
                if len(active) >= self._max_active:
                    return error_result(call.id, _full_msg(self._max_active))
                await self._store.add(item)
        except ScheduleStoreError as err:
            return store_down_result(call.id, err)
        if held is not None:
            content = f"already {_confirmation(held, self._zone)}; {_NOT_ADDED}"
        else:
            content = _confirmation(item, self._zone)
        return ToolResult(call_id=call.id, content=content, trust=Trust.TRUSTED)


def _confirmation(item: ScheduledItem, default_zone: DisplayZone) -> str:
    """The creation result for ``item``: its kind, id, due time and recurrence, never its text."""
    zone = effective_zone(item.rule, default_zone)
    due = zone.render(item.due_at)
    return f"scheduled {item.kind.value} {item.id}: due {due}{recurrence_phrase(item)}"


def _same_request(held: ScheduledItem, wanted: ScheduledItem) -> bool:
    """Whether an active item already does what ``wanted`` asks; a tainted one never stands in
    for a clean request, and the chat it was asked in is not compared.
    """
    return (
        held.kind is wanted.kind
        and _plain(held.text) == _plain(wanted.text)
        and held.due_at == wanted.due_at
        and held.every == wanted.every
        and held.rule == wanted.rule
        and held.model == wanted.model
        and (wanted.tainted or not held.tainted)
    )


def _plain(text: str) -> str:
    """The text two requests are compared by: case, spacing and a final full stop ignored."""
    return " ".join(text.casefold().split()).rstrip(".")


class ListScheduledTool:
    """Built-in ``list_scheduled``: the active schedules, ids included for cancelling."""

    def __init__(self, store: ScheduleStore, *, zone: DisplayZone = UTC_DISPLAY) -> None:
        self._store = store
        self._zone = zone

    @property
    def spec(self) -> ToolSpec:
        """No arguments; lists ids, kinds, due times, recurrence, and status."""
        return ToolSpec(
            name=LIST_SCHEDULED_TOOL_NAME,
            description=(
                "List the active scheduled reminders and tasks: id, kind, due time "
                f"({self._zone.name}), recurrence, and status. Use the id with cancel_scheduled."
            ),
            parameters={"type": "object", "properties": {}},
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """List active items; the listing is UNTRUSTED when any item is tainted."""
        try:
            items = await self._store.list_active()
        except ScheduleStoreError as err:
            return store_down_result(call.id, err)
        if not items:
            return ToolResult(call_id=call.id, content="no scheduled items", trust=Trust.TRUSTED)
        trust = Trust.UNTRUSTED if any(item.tainted for item in items) else Trust.TRUSTED
        return ToolResult(
            call_id=call.id,
            content="\n".join(describe_item(item, self._zone) for item in items),
            trust=trust,
        )
