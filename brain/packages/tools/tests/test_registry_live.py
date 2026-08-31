import asyncio
import os
import time
from functools import partial

import pytest

from cortex_core import BoundedToolRegistry, ToolCall, ToolError
from cortex_tools import ReconnectingMcpToolRegistry, streamable_http_session

_ENDPOINT = os.environ.get("CORTEX_TOOLS_ENDPOINT", "http://127.0.0.1:9000/mcp")
_READ_TOOL = os.environ.get("CORTEX_TOOLS_READ_TOOL", "read_text_file")
_READ_PATH = os.environ.get("CORTEX_TOOLS_READ_PATH", "/projects/hello.txt")


@pytest.mark.integration
async def test_registry_lists_and_calls_a_real_filesystem_server() -> None:
    registry = ReconnectingMcpToolRegistry(partial(streamable_http_session, _ENDPOINT))
    names = [spec.name for spec in await registry.describe_tools()]
    assert _READ_TOOL in names, f"{_READ_TOOL} not among {names}"
    result = await registry.invoke(
        ToolCall(id="live-1", name=_READ_TOOL, arguments={"path": _READ_PATH})
    )
    assert result.is_error is False
    assert result.content != ""


# Long enough that a loaded machine reaches the wait, short enough that the case costs a second
# and a half. The hang it bounds is absolute, so nothing here races the number.
_HANG_BOUND_S = 1.5


def _running(task: asyncio.Task[object]) -> str:
    """Return the name of the coroutine a task is running, which tells the fake server's own tasks
    apart from the client's.
    """
    return getattr(task.get_coro(), "__name__", "")


async def _swallow(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """A server that accepts the connection, reads the request, and never answers."""
    try:
        while await reader.read(4096):
            pass
    finally:
        writer.close()


@pytest.mark.integration
async def test_the_bound_cuts_a_real_session_that_will_never_answer() -> None:
    server = await asyncio.start_server(_swallow, "127.0.0.1", 0)
    async with server:
        port = server.sockets[0].getsockname()[1]
        url = f"http://127.0.0.1:{port}/mcp"
        bounded = BoundedToolRegistry(
            ReconnectingMcpToolRegistry(partial(streamable_http_session, url)),
            timeout_s=_HANG_BOUND_S,
        )
        before = set(asyncio.all_tasks())
        started = time.monotonic()
        with pytest.raises(ToolError, match="did not answer within"):
            await bounded.invoke(ToolCall(id="hang-1", name="read", arguments={"path": "/x"}))
        elapsed = time.monotonic() - started
        assert _HANG_BOUND_S <= elapsed < _HANG_BOUND_S * 4
        leaked = {task for task in asyncio.all_tasks() if _running(task) != "_swallow"}
        assert leaked <= before
