"""ReconnectingMcpToolRegistry against real sockets (host-only, ADR-0009).

Integration-marked: the first case needs a filesystem MCP server reachable at
``CORTEX_TOOLS_ENDPOINT`` (bring the sidecar up per docs/runbooks/tools-mcp.md), and the second
brings up its own listener, so both do real socket I/O and neither runs in CI. Run e.g.
`cd brain && CORTEX_TOOLS_ENDPOINT=http://127.0.0.1:9000/mcp \
uv run pytest -m integration --no-cov packages/tools`. The `--no-cov` matters, the 100%
gate in the workspace addopts would otherwise fail the run.
"""

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
    # The production shape: a reconnecting registry over a per-call structured session opener.
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
    """The name of what a live task is running, for telling the fake server's own apart."""
    return getattr(task.get_coro(), "__name__", "")


async def _swallow(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """A server that accepts the connection, reads the request, and answers nothing, ever."""
    try:
        while await reader.read(4096):
            pass
    finally:
        writer.close()


@pytest.mark.integration
async def test_the_bound_cuts_a_real_session_that_will_never_answer() -> None:
    """A sidecar that hangs is bounded, and the cut unwinds the real client cleanly.

    The one claim about `BoundedToolRegistry` that no fake can make. Beneath it sit an anyio task
    group, a cancel scope and an ``except*``, and an overrun cancels straight through all three:
    what has to come out is a `ToolError` (which every layer above knows how to handle) rather
    than an `ExceptionGroup`, a bare `CancelledError`, or a call that never returns. A hung
    server is the case the port had no answer for, since a *refused* dial raises on its own and a
    wedged one raises nothing at all, the MCP session's own wait for a response being unbounded.
    """
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
        # Nothing of the client survives the cut: a bound that raised while leaving the session's
        # own tasks running would leak one socket per dispatch and read exactly the same here.
        leaked = {task for task in asyncio.all_tasks() if _running(task) != "_swallow"}
        assert leaked <= before
