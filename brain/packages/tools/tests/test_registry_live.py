"""McpToolRegistry against a live streamable-http MCP server (host-only, ADR-0009).

Integration-marked: needs a filesystem MCP server reachable at ``CORTEX_TOOLS_ENDPOINT``
(bring the sidecar up per docs/runbooks/tools-mcp.md), never run in CI. Run e.g.
`cd brain && CORTEX_TOOLS_ENDPOINT=http://127.0.0.1:9000/mcp \
uv run pytest -m integration --no-cov packages/tools`. The `--no-cov` matters, the 100%
gate in the workspace addopts would otherwise fail the run.
"""

import os

import pytest

from cortex_core import ToolCall
from cortex_tools import McpToolRegistry

_ENDPOINT = os.environ.get("CORTEX_TOOLS_ENDPOINT", "http://127.0.0.1:9000/mcp")
_READ_TOOL = os.environ.get("CORTEX_TOOLS_READ_TOOL", "read_text_file")
_READ_PATH = os.environ.get("CORTEX_TOOLS_READ_PATH", "/projects/hello.txt")


@pytest.mark.integration
async def test_registry_lists_and_calls_a_real_filesystem_server() -> None:
    registry, close = await McpToolRegistry.connect(_ENDPOINT)
    try:
        names = [spec.name for spec in await registry.describe_tools()]
        assert _READ_TOOL in names, f"{_READ_TOOL} not among {names}"
        result = await registry.invoke(
            ToolCall(id="live-1", name=_READ_TOOL, arguments={"path": _READ_PATH})
        )
        assert result.is_error is False
        assert result.content != ""
    finally:
        await close()
