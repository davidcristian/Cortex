"""Find the stored rows a forget message permits a call to list, read without the call's text."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import replace

from cortex_core.forget_inside import bounded, may_keep
from cortex_core.forget_results import ALREADY_DELETED, NONE_FOUND
from cortex_core.memory import MemoryRecord
from cortex_core.memory_values import whole_values
from cortex_core.tools import ToolCall

Listing = Callable[[ToolCall], Awaitable[tuple[str, ...] | str]]


def call_text(call: ToolCall) -> str:
    """The text the call names, stripped; empty when the argument is missing or not a string."""
    value = call.arguments.get("text")
    return value.strip() if isinstance(value, str) else ""


async def permitted(
    call: ToolCall, told: Sequence[MemoryRecord], listing: Listing
) -> frozenset[str] | None:
    """The ids of the rows the call's message permits a call to list: each ``listing`` lists for a
    value of the message, and each of ``told`` holding none that ``may_keep`` does not keep.
    ``None`` when the call's text holds a digit or no stored row holds a value of the message."""
    query, values = call.stamp.query, whole_values(call.stamp.query).values()
    if any(char.isdigit() for char in call_text(call)):
        return None
    ids: set[str] = set()
    read = False
    for form in values:
        listed = await listing(replace(call, arguments={"text": form}))
        read = read or listed not in (NONE_FOUND, ALREADY_DELETED)
        ids.update(() if isinstance(listed, str) else listed)
    if not read:
        return None
    searches = [search for search in map(bounded, values) if search is not None]
    kept = {row.id for form in values for row in may_keep(told, (), query, form)}
    for row in told:
        if row.id not in kept and not any(search.search(row.text) for search in searches):
            ids.add(row.id)
    return frozenset(ids)
