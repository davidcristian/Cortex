"""The ``cancel_scheduled`` / ``snooze_scheduled`` / ``edit_scheduled`` lifecycle verbs (ADR-0025).

Split from ``schedule_tools.py`` by responsibility (the 300-line cap): creation and listing
stay there, the verbs that change an existing item's lifecycle live here, together with the
result helpers both modules share. Cortex-only like their siblings (built-ins never reach
subagents). ``cancel``/``snooze`` carry no taint gate: postponing or deleting an existing
human-visible item is reversible-by-recreation and never echoes stored text, so a tainted
turn keeps both. ``edit`` is the exception, because a retext injects new content: the editing
turn's taint ORs onto the item (the listing then badges it), and an autonomous *task* cannot
be edited on a tainted turn at all (the creation-side refusal, since a task instruction
authored by injected content is a standing directive). Bad arguments and a down store both
become ``is_error`` results, never exceptions.
"""

from dataclasses import replace
from datetime import datetime

from cortex_core.errors import ScheduleStoreError
from cortex_core.ports import Clock, ScheduleStore
from cortex_core.schedule import ScheduleKind, ScheduleStatus
from cortex_core.schedule_args import MIN_EVERY_SECONDS
from cortex_core.schedule_calendar import CalendarRule
from cortex_core.schedule_day_args import day_selector_properties, in_zone_property
from cortex_core.schedule_time import UTC_DISPLAY, UTC_ZONE_CONTEXT, DisplayZone, ZoneContext
from cortex_core.schedule_transitions import ScheduleEdit
from cortex_core.schedule_verb_args import parse_edit, parse_for_seconds
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

CANCEL_SCHEDULED_TOOL_NAME = "cancel_scheduled"
SNOOZE_SCHEDULED_TOOL_NAME = "snooze_scheduled"
EDIT_SCHEDULED_TOOL_NAME = "edit_scheduled"

_STORE_DOWN = "the schedule store is unavailable"
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


def effective_zone(rule: CalendarRule | None, default_zone: DisplayZone) -> DisplayZone:
    """The zone a calendar item's due time renders in: the rule's own if it has one, else the
    deployment default (ADR-0025 per-rule addendum, shared with ``schedule_tools``).

    A per-zone rule shows the wall time it names (``09:00-04:00``) rather than the same instant
    printed in another zone (``16:00+03:00``), so a listing and the rule's ``describe`` agree.
    An interval item or a zone-less rule renders in the deployment zone exactly as before.
    """
    return rule.zone if rule is not None and rule.zone is not None else default_zone


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
            return error_result(call.id, "'id' must be a non-empty string")
        try:
            cancelled = await self._store.cancel(item_id)
        except ScheduleStoreError as err:
            return store_down_result(call.id, err)
        if not cancelled:
            return error_result(call.id, f"no scheduled item {item_id}")
        return ToolResult(call_id=call.id, content=f"cancelled {item_id}", trust=Trust.TRUSTED)


class SnoozeScheduledTool:
    """Built-in ``snooze_scheduled``: postpone a schedule's next fire from now (snooze addendum).

    Works on one-shots and recurring items alike: a recurring snooze moves only the *next*
    occurrence, and the store pins the recurrence grid via ``anchor`` so the series keeps its
    original cadence afterward (ADR-0025 occurrence-snooze addendum), rather than re-anchoring
    the whole series. Only a FIRING item is refused (the in-flight fire settles first).
    """

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
        """Apply the snooze; a correction string when it cannot, None on success.

        The read is advisory (unknown / firing get named corrections); the fenced ``snooze``
        is authoritative, so a cancel or claim racing this call surfaces as the
        changed-underneath correction rather than a lost update. Recurring items are allowed:
        the store moves only the next occurrence and pins the grid (ADR-0025 occurrence-snooze).
        """
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
    """Built-in ``edit_scheduled``: change a schedule's text and/or recurrence in place.

    Retext (``text``) and re-recur (``every_seconds``: a new interval, or ``0`` to stop
    repeating; or ``at_time``/``on_days``: a wall-clock rule) without cancel-and-recreate. An
    interval change leaves the next due time untouched, so it alters the cadence of future
    re-arms only; setting a **rule** re-derives the next occurrence from the rule itself, since
    a rule is its own grid and a pinned due time would name a fire the rule does not
    (ADR-0025 rule-edit addendum). A FIRING item is refused (the in-flight fire settles
    first); a tainted turn may edit a reminder (the item then becomes tainted) but not a task
    (the creation-side refusal). No stored text ever rides the result.
    """

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
            correction = await self._edit(item_id, edit)
        except ScheduleStoreError as err:
            return store_down_result(call.id, err)
        if correction is not None:
            return error_result(call.id, correction)
        content = f"edited {item_id}"
        if edit.rule is not None:
            # Only the rule branch moves the timing, so only it owes the new due time, rendered in
            # the rule's own zone when it named one (ADR-0025 per-rule addendum).
            zone = effective_zone(edit.rule.rule, self._zone)
            content = f"{content}: now due {zone.render(edit.rule.due_at)}"
        return ToolResult(call_id=call.id, content=content, trust=Trust.TRUSTED)

    async def _edit(self, item_id: str, edit: ScheduleEdit) -> str | None:
        """Advisory guards (unknown / firing / tainted-task), then the fenced edit.

        The read is advisory; the fenced ``edit`` is authoritative, so a cancel or claim racing
        this call surfaces as the changed-underneath correction rather than a lost update. The
        tainted-task refusal is deterministic (the dispatcher's stamp on ``edit.tainted``, never
        a model claim), matching creation: a task instruction is never rewritten under taint.
        """
        item = await self._store.get(item_id)
        if item is None:
            return f"no scheduled item {item_id}"
        if item.status is ScheduleStatus.FIRING:
            return f"{item_id} is firing right now; try again in a moment"
        if item.kind is ScheduleKind.TASK and edit.tainted:
            return _EDIT_TAINTED_TASK
        if not await self._store.edit(item_id, edit):
            return (
                f"{item_id} changed underneath (fired or cancelled); use list_scheduled to re-check"
            )
        return None
