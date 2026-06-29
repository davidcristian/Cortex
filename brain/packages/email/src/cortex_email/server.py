"""FastMCP server exposing the read-only email tools over an EmailReader (ADR-0009).

Three read-only tools (``list_folders``, ``search_emails``, ``read_email``). ``build_server``
wires them to an `EmailReader` (covered in-process via ``FastMCP.call_tool``); ``main`` reads the
env config, builds the imap-tools-backed reader, and runs the server over streamable-http. The
sync IMAP work runs in a thread so the async MCP loop is never blocked.
"""
# The tool handlers are registered via the @server.tool() decorator (a side effect), so
# pyright's "not accessed" check is a false positive for this small handler module.
# pyright: reportUnusedFunction=false

import asyncio

from mcp.server.fastmcp import FastMCP

from cortex_email.config import EmailConfig
from cortex_email.imap import ImapMailbox
from cortex_email.reader import EmailReader

_SERVER_HOST = "0.0.0.0"  # noqa: S104 - the sidecar binds its container interface; compose publishes loopback-only
_SERVER_PORT = 9100
_DEFAULT_SEARCH_LIMIT = 20


def build_server(reader: EmailReader) -> FastMCP:
    """Register the read-only email tools on a FastMCP server backed by ``reader``.

    Each tool returns a single readable string: the model consumes tool results as text, and
    a list/dict return would be split into per-item content blocks a text client cannot
    reassemble. One string keeps the result clean end to end.
    """
    server = FastMCP(
        "cortex-email", host=_SERVER_HOST, port=_SERVER_PORT, streamable_http_path="/mcp"
    )

    @server.tool()
    async def list_folders() -> str:
        """List the mailbox folders available to read, one per line."""
        return "\n".join(await asyncio.to_thread(reader.folders))

    @server.tool()
    async def search_emails(folder: str, query: str, limit: int = _DEFAULT_SEARCH_LIMIT) -> str:
        """Search one folder with an IMAP query; return one summary line per match."""
        summaries = await asyncio.to_thread(reader.search, folder, query, limit)
        if not summaries:
            return "(no matching messages)"
        return "\n".join(f"[{s.uid}] {s.date} | {s.sender} | {s.subject}" for s in summaries)

    @server.tool()
    async def read_email(folder: str, uid: str) -> str:
        """Read one message in full (headers + plain-text body) by its uid."""
        detail = await asyncio.to_thread(reader.read, folder, uid)
        if detail is None:
            return f"message {uid} not found in {folder}"
        return (
            f"From: {detail.sender}\nTo: {detail.recipients}\n"
            f"Date: {detail.date}\nSubject: {detail.subject}\n\n{detail.body}"
        )

    return server


def main() -> None:
    """Run the read-only email MCP server from the environment (streamable-http)."""
    reader = EmailReader(ImapMailbox(EmailConfig()))
    build_server(reader).run(transport="streamable-http")
