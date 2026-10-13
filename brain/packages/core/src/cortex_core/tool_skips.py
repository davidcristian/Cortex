"""The tool servers a listing left out, collected for the turn that listed and shown to the user."""

from collections.abc import Sequence
from contextvars import ContextVar
from typing import Protocol

from cortex_core.events import FORGOING_STATE, StatusUpdate
from cortex_core.progress import ProgressSink
from cortex_core.tools import ToolSpec

# Set only while one listing runs, so a skip counts for the task whose own walk made it.
_listing: ContextVar[list[str] | None] = ContextVar("cortex_tool_skips", default=None)

_ONE = "tool server is not answering"
_SEVERAL = "tool servers are not answering"


class ToolLister(Protocol):
    """Anything that lists the tools a turn may call."""

    async def describe_tools(self) -> Sequence[ToolSpec]: ...


def note_skipped(name: str) -> None:
    """Add ``name`` to the listing this task is running, when one is collecting skips."""
    names = _listing.get()
    if names is not None and name not in names:
        names.append(name)


def skipped_detail(names: Sequence[str]) -> str:
    """The status sentence for a turn answered without the tools of the servers ``names``."""
    if len(names) == 1:
        return f"the {names[0]} {_ONE}, so this turn is answered without its tools"
    listed = f"{', '.join(names[:-1])} and {names[-1]}"
    return f"the {listed} {_SEVERAL}, so this turn is answered without their tools"


async def list_tools(lister: ToolLister, progress: ProgressSink | None) -> Sequence[ToolSpec]:
    """List the turn's tools, and tell ``progress`` which tool servers the listing left out."""
    names: list[str] = []
    token = _listing.set(names)
    try:
        specs = await lister.describe_tools()
    finally:
        _listing.reset(token)
    if names and progress is not None:
        await progress.emit(StatusUpdate(state=FORGOING_STATE, detail=skipped_detail(names)))
    return specs
