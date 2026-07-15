"""FastMCP server exposing the email tools over an EmailReader (ADR-0009, ADR-0022).

Three read tools (``list_folders``, ``search_emails``, ``read_email``) always register;
the ``send_email`` write twin registers **only** when a sender is passed (``main`` builds
one only under ``CORTEX_EMAIL_SEND_ENABLED=true``, ADR-0022), so an unconfigured server is
byte-for-byte the read-only Slice 6 sidecar. ``build_server`` wires them (covered
in-process via ``FastMCP.call_tool``); ``main`` reads the env config and runs the server
over streamable-http. Sync IMAP/SMTP work runs in a thread so the async MCP loop is never
blocked. Brain-side, ``send_email`` is stamped ``gated`` at the composition root
(``CORTEX_TOOLS_GATED``). The annotations here are advisory metadata, never authority.
"""
# The tool handlers are registered via the @server.tool() decorator (a side effect), so
# pyright's "not accessed" check is a false positive for this small handler module.
# pyright: reportUnusedFunction=false

import asyncio
from collections.abc import Sequence

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from cortex_email.config import EmailConfig, SmtpConfig
from cortex_email.imap import ImapMailbox
from cortex_email.reader import EmailReader
from cortex_email.smtp import EmailSender, SmtpSender
from cortex_email.values import EmailAttachment, EmailDraft

_SERVER_HOST = "0.0.0.0"  # noqa: S104 - the sidecar binds its container interface; compose publishes loopback-only
_SERVER_PORT = 9100
_DEFAULT_SEARCH_LIMIT = 20


def build_server(reader: EmailReader, sender: EmailSender | None = None) -> FastMCP:
    """Register the email tools on a FastMCP server: reads always, send only with a sender.

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

    if sender is not None:
        # Advisory MCP metadata only. The enforcing declaration is the brain-side
        # CORTEX_TOOLS_GATED overlay (ADR-0022): a sidecar must not be able to
        # self-declare its way past the gate, in either direction.
        @server.tool(
            annotations=ToolAnnotations(
                readOnlyHint=False, destructiveHint=True, openWorldHint=True
            )
        )
        # PLR0913's ceiling is a dependency-injection one (see ruff.toml): bundle collaborators
        # before asking for a seventh. These are not collaborators, they are the draft's fields
        # as the model sees them, and this signature IS the advertised JSON schema, so folding
        # them into an object would rewrite a working tool contract to satisfy a lint rule.
        async def send_email(  # noqa: PLR0913
            to: str,
            subject: str,
            body: str,
            cc: str = "",
            bcc: str = "",
            html: str = "",
            attachments: Sequence[EmailAttachment] = (),
        ) -> str:
            """Send an email as the configured account (outbound, irreversible; it runs only
            with the user's explicit approval). ``to``/``cc``/``bcc`` are comma-separated
            address lists (``cc``/``bcc`` optional); ``body`` is the plain-text message; pass
            ``html`` to add a rich alternative shown as the body where the reader supports it.
            ``attachments`` attaches text you have written, as
            ``{"filename": "notes.md", "content": "...", "subtype": "markdown"}`` objects
            (``subtype`` is the text flavour: plain, markdown, csv, calendar; default plain).
            Attachments carry text only, so a file on disk cannot be attached."""
            return await asyncio.to_thread(
                sender.send,
                EmailDraft(to, subject, body, cc, bcc, html, tuple(attachments)),
            )

    return server


def main() -> None:
    """Run the email MCP server from the environment (streamable-http).

    The send path is opt-in: a sender exists only under CORTEX_EMAIL_SEND_ENABLED=true
    (with credentials validated at startup). Otherwise this is the read-only server.
    """
    reader = EmailReader(ImapMailbox(EmailConfig()))
    smtp = SmtpConfig()
    sender = SmtpSender(smtp) if smtp.enabled else None
    build_server(reader, sender).run(transport="streamable-http")
