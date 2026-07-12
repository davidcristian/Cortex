"""The ``cancel_scheduled`` / ``snooze_scheduled`` lifecycle verbs (ADR-0025).

Split from ``schedule_tools.py`` by responsibility (the 300-line cap): creation and listing
stay there, the verbs that change an existing item's lifecycle live here, together with the
result helpers both modules share. Cortex-only like their siblings (built-ins never reach
subagents). Neither verb carries a taint gate: cancelling or postponing an existing
human-visible item is reversible-by-recreation and never echoes stored text, so a tainted
turn keeps both (the creation-side tainted-task refusal is where injected content is
stopped). Bad arguments and a down store both become ``is_error`` results, never exceptions.
"""

from datetime import UTC, datetime

from cortex_core.errors import ScheduleStoreError
from cortex_core.ports import Clock, ScheduleStore
from cortex_core.schedule import ScheduleStatus
from cortex_core.schedule_args import MIN_EVERY_SECONDS, parse_for_seconds
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

CANCEL_SCHEDULED_TOOL_NAME = "cancel_scheduled"
SNOOZE_SCHEDULED_TOOL_NAME = "snooze_scheduled"

_STORE_DOWN = "the schedule store is unavailable"


def store_down_result(call_id: str, err: ScheduleStoreError) -> ToolResult:
    """The trusted is_error result a down store becomes (shared with ``schedule_tools``)."""
    return ToolResult(
        call_id=call_id, content=f"{_STORE_DOWN}: {err}", is_error=True, trust=Trust.TRUSTED
    )


def error_result(call_id: str, message: str) -> ToolResult:
    """A trusted correction the model can act on (shared with ``schedule_tools``)."""
    return ToolResult(call_id=call_id, content=message, is_error=True, trust=Trust.TRUSTED)


def utc_str(moment: datetime) -> str:
    """One canonical UTC rendering for specs and results (shared with ``schedule_tools``)."""
    return moment.astimezone(UTC).isoformat(timespec="seconds")


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
    """Built-in ``snooze_scheduled``: postpone a one-shot schedule from now (snooze addendum).

    One-shots only: recurrence anchors on ``due_at`` (``next_due``), so a snoozed recurring
    item would silently re-anchor its whole series; the refusal names the workaround.
    """

    def __init__(self, store: ScheduleStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    @property
    def spec(self) -> ToolSpec:
        """Takes the id plus a relative delay; the store computes the absolute time."""
        return ToolSpec(
            name=SNOOZE_SCHEDULED_TOOL_NAME,
            description=(
                "Postpone a one-shot scheduled reminder or task: it fires 'for_seconds' "
                "from now instead of its current due time. Recurring schedules cannot be "
                "snoozed (cancel and re-create instead). Use the id from list_scheduled."
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
        content = f"snoozed {item_id}: now due {utc_str(until)}"
        return ToolResult(call_id=call.id, content=content, trust=Trust.TRUSTED)

    async def _snooze(self, item_id: str, until: datetime) -> str | None:
        """Apply the snooze; a correction string when it cannot, None on success.

        The read is advisory (unknown / recurring / firing get named corrections); the
        fenced ``snooze`` is authoritative, so a cancel or claim racing this call surfaces
        as the changed-underneath correction rather than a lost update.
        """
        item = await self._store.get(item_id)
        if item is None:
            return f"no scheduled item {item_id}"
        if item.every is not None:
            return (
                f"{item_id} is recurring and cannot be snoozed; cancel it and "
                "schedule a new one instead"
            )
        if item.status is ScheduleStatus.FIRING:
            return f"{item_id} is firing right now; try again in a moment"
        if not await self._store.snooze(item_id, until=until):
            return (
                f"{item_id} changed underneath (fired or cancelled); use list_scheduled to re-check"
            )
        return None
