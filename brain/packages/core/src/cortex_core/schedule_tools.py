"""The ``schedule_task`` / ``list_scheduled`` built-ins (ADR-0025).

Cortex-only by construction (built-ins never reach subagents, per ADR-0010/0013), so a subagent
cannot re-schedule: self-perpetuation is bounded exactly like depth-1 bounds delegation.
Ungated by default, as creating a schedule is reversible (``cancel_scheduled`` sticks, the store's
fenced protocol). Two creation bounds apply: the active-items cap, and the **tainted-task
refusal** (a turn that has read untrusted content cannot create a ``kind: "task"`` item at all;
an autonomous agent instruction authored by injected content is a standing directive, not a
reminder a human vets). The ``schedule_task`` spec is rebuilt per ``describe_tools`` walk and
carries the current UTC time from the injected ``Clock``. The model cannot otherwise compute an
absolute ``at``. Creation results are TRUSTED and never echo the stored text; the listing
does echo text, so it is TRUSTED only when every listed item is clean (the spawn aggregate rule, so
hostile text is fenced and re-taints the turn instead of laundering through a trusted result).
Bad arguments and a down store both become ``is_error`` results, never exceptions. The
lifecycle verbs (``cancel_scheduled``/``snooze_scheduled``/``edit_scheduled``) live in
``schedule_verbs.py`` (the line-cap split), which also owns the result helpers shared here.
"""

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from cortex_core.errors import ScheduleStoreError
from cortex_core.ports import Clock, ScheduleStore
from cortex_core.schedule import ScheduledItem, ScheduleKind, ScheduleStatus
from cortex_core.schedule_args import MIN_EVERY_SECONDS, parse_schedule
from cortex_core.schedule_day_args import day_selector_properties
from cortex_core.schedule_time import UTC_DISPLAY, DisplayZone
from cortex_core.schedule_verbs import error_result, store_down_result
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

SCHEDULE_TOOL_NAME = "schedule_task"
LIST_SCHEDULED_TOOL_NAME = "list_scheduled"

TAINTED_TASK_MSG = (
    "cannot schedule an autonomous task on a turn that has read untrusted external "
    "content; schedule a reminder instead, or re-ask in a fresh turn"
)


def _uuid4_id() -> str:
    """Default item-id factory; injectable so tests can pin ids."""
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
        zone: DisplayZone = UTC_DISPLAY,
        item_id_factory: Callable[[], str] = _uuid4_id,
    ) -> None:
        self._store = store
        self._clock = clock
        self._tasks_enabled = tasks_enabled
        self._max_active = max_active
        self._zone = zone
        self._item_id_factory = item_id_factory

    @property
    def spec(self) -> ToolSpec:
        """Rebuilt per walk: carries the current local time and is honest about task wiring."""
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
                    "Absolute due time, ISO-8601, e.g. 2026-07-12T18:00:00. An explicit offset "
                    f"is honored; without one it is read as {self._zone.name} local time."
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
            "at_time": {
                "type": "string",
                "description": (
                    f"Recurring wall-clock time, 24-hour HH:MM in {self._zone.name}, e.g. 09:00. "
                    "Use this for 'every day at 9' rather than 'every_seconds': it keeps the "
                    "same clock time across daylight saving. Alternative to 'at'/'in_seconds'."
                ),
            },
            **day_selector_properties(),
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
                "Provide 'at' (ISO-8601) or 'in_seconds' (delay from now), "
                "and add 'every_seconds' to recur; or provide 'at_time' (HH:MM) with "
                "optional 'on_days', 'on_month_days', or 'on_dates' to recur at a "
                "wall-clock time."
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
        parsed = parse_schedule(
            call.arguments, now=now, tasks_enabled=self._tasks_enabled, zone=self._zone
        )
        if isinstance(parsed, str):
            return error_result(call.id, parsed)
        if parsed.kind is ScheduleKind.TASK and call.stamp.tainted:
            return error_result(call.id, TAINTED_TASK_MSG)
        try:
            if len(await self._store.list_active()) >= self._max_active:
                return error_result(
                    call.id,
                    f"the schedule is full ({self._max_active} active items); cancel one first",
                )
            item = ScheduledItem(
                id=self._item_id_factory(),
                kind=parsed.kind,
                text=parsed.text,
                # Attribution from the dispatcher's stamp (ADR-0027): the origin chat rides
                # the record (provenance, never display; the listing does not render it).
                session_id=call.stamp.session_id,
                due_at=parsed.due_at,
                created_at=now,
                every=parsed.every,
                rule=parsed.rule,
                model=parsed.model,
                tainted=call.stamp.tainted,
            )
            await self._store.add(item)
        except ScheduleStoreError as err:
            return store_down_result(call.id, err)
        content = (
            f"scheduled {parsed.kind.value} {item.id}: "
            f"due {self._zone.render(parsed.due_at)}{_recurrence(item)}"
        )
        return ToolResult(call_id=call.id, content=content, trust=Trust.TRUSTED)


def _recurrence(item: ScheduledItem) -> str:
    """How the item repeats, as a leading-comma phrase; empty for a one-shot.

    Shared by the creation confirmation and the listing line so the two never describe the
    same schedule differently. A calendar rule speaks wall-clock ("every mon, fri at 07:30")
    rather than seconds, which is the whole point of carrying it as a rule.
    """
    if item.rule is not None:
        return f", {item.rule.describe()}"
    if item.every is not None:
        return f", every {int(item.every.total_seconds())}s"
    return ""


def _describe(item: ScheduledItem, zone: DisplayZone) -> str:
    """One listing line per item; the stored text rides at the end, provenance marked."""
    recurring = _recurrence(item)
    fired = ", fired awaiting delivery" if item.deliverable_since is not None else ""
    firing = ", firing now" if item.status is ScheduleStatus.FIRING else ""
    tainted = ", from untrusted content" if item.tainted else ""
    marks = f"{recurring}{firing}{fired}{tainted}"
    line = f"[{item.id}] {item.kind.value} due {zone.render(item.due_at)}{marks}: {item.text}"
    if item.last_outcome is not None:
        line += f"\n    last outcome: {item.last_outcome}"
    return line


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
        """List active items; the listing is UNTRUSTED iff any item carries taint.

        A tainted item's text is attacker-influenced: fencing the whole listing (and
        re-tainting the turn) beats laundering it through a trusted result (ADR-0025).
        """
        try:
            items = await self._store.list_active()
        except ScheduleStoreError as err:
            return store_down_result(call.id, err)
        if not items:
            return ToolResult(call_id=call.id, content="no scheduled items", trust=Trust.TRUSTED)
        trust = Trust.UNTRUSTED if any(item.tainted for item in items) else Trust.TRUSTED
        return ToolResult(
            call_id=call.id,
            content="\n".join(_describe(item, self._zone) for item in items),
            trust=trust,
        )
