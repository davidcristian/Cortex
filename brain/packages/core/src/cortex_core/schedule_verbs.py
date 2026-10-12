"""The ``cancel_scheduled`` / ``snooze_scheduled`` / ``edit_scheduled`` lifecycle verbs."""

from dataclasses import replace
from datetime import datetime

from cortex_core.errors import ScheduleStoreError
from cortex_core.ports import Clock, ScheduleStore
from cortex_core.schedule import ScheduleKind, ScheduleStatus
from cortex_core.schedule_args import MIN_EVERY_SECONDS
from cortex_core.schedule_day_args import day_selector_properties, in_zone_property
from cortex_core.schedule_render import describe_item, effective_zone
from cortex_core.schedule_time import UTC_DISPLAY, UTC_ZONE_CONTEXT, DisplayZone, ZoneContext
from cortex_core.schedule_transitions import ScheduleEdit
from cortex_core.schedule_verb_args import parse_edit, parse_for_seconds
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

CANCEL_SCHEDULED_TOOL_NAME = "cancel_scheduled"
SNOOZE_SCHEDULED_TOOL_NAME = "snooze_scheduled"
EDIT_SCHEDULED_TOOL_NAME = "edit_scheduled"

_STORE_DOWN = "the schedule store is unavailable"
_CARD_LEAD = "Deletes this scheduled item for good, with no undo: "
# The card is read before Approve, so a long stored text is cut rather than pushing it away.
CARD_CHARS = 400
_EDIT_TAINTED_TASK = (
    "cannot edit an autonomous task on a turn that has read untrusted external content; "
    "edit a reminder instead, or re-ask in a fresh turn"
)


def store_down_result(call_id: str, err: ScheduleStoreError) -> ToolResult:
    """The trusted is_error result a down store becomes (shared with ``schedule_tools``)."""
    return ToolResult(
        call_id=call_id, content=f"{_STORE_DOWN}: {err}", is_error=True, trust=Trust.TRUSTED
    )


def error_result(call_id: str, message: str) -> ToolResult:
    """A trusted correction the model can act on (shared with ``schedule_tools``)."""
    return ToolResult(call_id=call_id, content=message, is_error=True, trust=Trust.TRUSTED)


class CancelScheduledTool:
    """Built-in ``cancel_scheduled``: delete a schedule outright, mid-fire included."""

    def __init__(self, store: ScheduleStore, *, zone: DisplayZone = UTC_DISPLAY) -> None:
        self._store = store
        self._zone = zone

    @property
    def spec(self) -> ToolSpec:
        """Takes the id a listing (or creation confirmation) reported; the user confirms it."""
        return ToolSpec(
            name=CANCEL_SCHEDULED_TOOL_NAME,
            description="Cancel a scheduled reminder or task by its id (see list_scheduled).",
            parameters={
                "type": "object",
                "properties": {"id": {"type": "string", "description": "The scheduled item's id."}},
                "required": ["id"],
            },
            confirm_required=True,
        )

    async def card(self, call: ToolCall) -> str:
        """The confirmation card's text: the stored item the call would delete, read now."""
        item_id = call.arguments.get("id")
        try:
            item = await self._store.get(item_id) if isinstance(item_id, str) else None
        except ScheduleStoreError:
            return f"{_CARD_LEAD}item {item_id}, which cannot be read: {_STORE_DOWN}."
        if item is None:
            return f"{_CARD_LEAD}item {item_id}, which is not on the schedule."
        line = " ".join(describe_item(item, self._zone).split())
        if len(line) > CARD_CHARS:
            line = line[: CARD_CHARS - 3] + "..."
        return f"{_CARD_LEAD}{line}"

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Cancel by id; unknown ids are a correctable error, never an exception."""
        item_id = call.arguments.get("id")
        if not isinstance(item_id, str) or not item_id:
            return error_result(call.id, "'id' must be a non-empty string")
        try:
            cancelled = await self._store.cancel(item_id)
        except ScheduleStoreError as err:
            return store_down_result(call.id, err)
        if not cancelled:
            return error_result(call.id, f"no scheduled item {item_id}")
        return ToolResult(call_id=call.id, content=f"cancelled {item_id}", trust=Trust.TRUSTED)


class SnoozeScheduledTool:
    """Built-in ``snooze_scheduled``: postpone a schedule's next fire from now."""

    def __init__(
        self, store: ScheduleStore, clock: Clock, *, zone: DisplayZone = UTC_DISPLAY
    ) -> None:
        self._store = store
        self._clock = clock
        self._zone = zone

    @property
    def spec(self) -> ToolSpec:
        """Takes the id plus a relative delay; the store computes the absolute time."""
        return ToolSpec(
            name=SNOOZE_SCHEDULED_TOOL_NAME,
            description=(
                "Postpone a scheduled reminder or task: its next fire moves to 'for_seconds' "
                "from now instead of its current due time. For a recurring schedule this moves "
                "only the next occurrence; the series keeps its original cadence afterward. "
                "Use the id from list_scheduled."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "The scheduled item's id."},
                    "for_seconds": {
                        "type": "number",
                        "minimum": MIN_EVERY_SECONDS,
                        "description": "How far from now to postpone, in seconds.",
                    },
                },
                "required": ["id", "for_seconds"],
            },
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Validate, then apply the fenced transition; corrections come back as errors."""
        item_id = call.arguments.get("id")
        if not isinstance(item_id, str) or not item_id:
            return error_result(call.id, "'id' must be a non-empty string")
        delay = parse_for_seconds(call.arguments)
        if isinstance(delay, str):
            return error_result(call.id, delay)
        until = self._clock.now() + delay
        try:
            correction = await self._snooze(item_id, until)
        except ScheduleStoreError as err:
            return store_down_result(call.id, err)
        if correction is not None:
            return error_result(call.id, correction)
        content = f"snoozed {item_id}: now due {self._zone.render(until)}"
        return ToolResult(call_id=call.id, content=content, trust=Trust.TRUSTED)

    async def _snooze(self, item_id: str, until: datetime) -> str | None:
        """Apply the snooze; a correction string when it cannot, None on success."""
        item = await self._store.get(item_id)
        if item is None:
            return f"no scheduled item {item_id}"
        if item.status is ScheduleStatus.FIRING:
            return f"{item_id} is firing right now; try again in a moment"
        if not await self._store.snooze(item_id, until=until):
            return (
                f"{item_id} changed underneath (fired or cancelled); use list_scheduled to re-check"
            )
        return None


class EditScheduledTool:
    """Built-in ``edit_scheduled``: change a schedule's text and/or recurrence in place."""

    def __init__(
        self, store: ScheduleStore, clock: Clock, *, zones: ZoneContext = UTC_ZONE_CONTEXT
    ) -> None:
        self._store = store
        self._clock = clock
        self._zone = zones.default
        self._resolve_zone = zones.resolver

    @property
    def spec(self) -> ToolSpec:
        """Takes the id plus the optional changes; at least one change is required."""
        return ToolSpec(
            name=EDIT_SCHEDULED_TOOL_NAME,
            description=(
                "Change a scheduled reminder or task by its id: set new 'text', and/or change "
                "how it repeats with either 'every_seconds' (a fixed interval, 0 to stop "
                f"repeating) or 'at_time' (a wall-clock time in {self._zone.name}, or in "
                "'in_zone', optionally on given 'on_days', 'on_month_days', or 'on_dates'). An "
                "'every_seconds' change leaves the next due time alone; "
                "'at_time' moves it to that rule's next occurrence. Use the id from "
                "list_scheduled."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "The scheduled item's id."},
                    "text": {"type": "string", "description": "New text (optional)."},
                    "every_seconds": {
                        "type": "number",
                        "description": (
                            f"New repeat interval in seconds (min {MIN_EVERY_SECONDS}), or "
                            "0 to stop repeating (optional)."
                        ),
                    },
                    "at_time": {
                        "type": "string",
                        "description": (
                            "New wall-clock repeat time as HH:MM (optional); replaces any "
                            "'every_seconds' interval this schedule had."
                        ),
                    },
                    **day_selector_properties(),
                    **in_zone_property(),
                },
                "required": ["id"],
            },
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Validate, then apply the fenced edit; corrections come back as errors."""
        item_id = call.arguments.get("id")
        if not isinstance(item_id, str) or not item_id:
            return error_result(call.id, "'id' must be a non-empty string")
        parsed = parse_edit(
            call.arguments, now=self._clock.now(), zone=self._zone, resolve_zone=self._resolve_zone
        )
        if isinstance(parsed, str):
            return error_result(call.id, parsed)
        edit = replace(parsed, tainted=call.stamp.tainted)
        try:
            correction = await self._edit(item_id, edit, live_taint=call.stamp.live_taint)
        except ScheduleStoreError as err:
            return store_down_result(call.id, err)
        if correction is not None:
            return error_result(call.id, correction)
        content = f"edited {item_id}"
        if edit.rule is not None:
            zone = effective_zone(edit.rule.rule, self._zone)
            content = f"{content}: now due {zone.render(edit.rule.due_at)}"
        return ToolResult(call_id=call.id, content=content, trust=Trust.TRUSTED)

    async def _edit(self, item_id: str, edit: ScheduleEdit, *, live_taint: bool) -> str | None:
        """Advisory guards (unknown / firing / tainted-task), then the fenced edit."""
        item = await self._store.get(item_id)
        if item is None:
            return f"no scheduled item {item_id}"
        if item.status is ScheduleStatus.FIRING:
            return f"{item_id} is firing right now; try again in a moment"
        if item.kind is ScheduleKind.TASK and live_taint:
            return _EDIT_TAINTED_TASK
        if not await self._store.edit(item_id, edit):
            return (
                f"{item_id} changed underneath (fired or cancelled); use list_scheduled to re-check"
            )
        return None
