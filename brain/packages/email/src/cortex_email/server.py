"""FastMCP server exposing the email tools over an EmailReader (ADR-0009, ADR-0022)."""
# The tool handlers are registered via the @server.tool() decorator (a side effect), so
# pyright's "not accessed" check is a false positive for this small handler module.
# pyright: reportUnusedFunction=false

import asyncio
from collections.abc import Sequence
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from cortex_email.config import EmailConfig, SmtpConfig
from cortex_email.errors import FolderUnknownError, SearchRefusedError
from cortex_email.imap import ImapMailbox
from cortex_email.reader import EmailReader
from cortex_email.smtp import EmailSender, SmtpSender
from cortex_email.values import (
    ATTACHMENTS_HELP,
    FOLDER_HELP,
    NOT_FOUND,
    SEARCH_LIMIT_HELP,
    SEARCH_QUERY_HELP,
    UID_HELP,
    EmailAttachment,
    EmailDraft,
)

_SERVER_HOST = "0.0.0.0"  # noqa: S104 - the sidecar binds its container interface; compose publishes loopback-only
_SERVER_PORT = 9100
_DEFAULT_SEARCH_LIMIT = 20

_SOURCE_META_KEY = "cortex/source"

_SENDER_KIND = "sender"

# The two field names that declaration is written under, bound here and again in `cortex_tools`,
# which reads them, for the reason the key is: a field renamed on one side alone would read as no
# declaration, and the same scan holds each pair of bindings equal.
_KIND_FIELD = "kind"
_VALUE_FIELD = "value"


def _one_text(text: str, *, failed: bool = False) -> CallToolResult:
    """One readable text block as the whole tool result, ``isError`` when it reports a failure."""
    return CallToolResult(content=[TextContent(type="text", text=text)], isError=failed)


def _sender_source(sender: str) -> dict[str, dict[str, str]] | None:
    """The result ``_meta`` declaring ``sender`` as the message's source, or ``None`` when absent.

    A message with no ``From`` header declares nothing rather than an empty sender; the brain drops
    an empty value anyway, so this keeps the wire clean.
    """
    if not sender:
        return None
    return {_SOURCE_META_KEY: {_KIND_FIELD: _SENDER_KIND, _VALUE_FIELD: sender}}


def build_server(reader: EmailReader, sender: EmailSender | None = None) -> FastMCP:
    """Register the email tools on a FastMCP server: reads always, send only with a sender."""
    server = FastMCP(
        "cortex-email", host=_SERVER_HOST, port=_SERVER_PORT, streamable_http_path="/mcp"
    )

    @server.tool()
    async def list_folders() -> str:
        """List the mailbox folders available to read, one per line."""
        return "\n".join(await asyncio.to_thread(reader.folders))

    @server.tool()
    async def search_emails(
        folder: Annotated[str, Field(description=FOLDER_HELP)],
        query: Annotated[str, Field(description=SEARCH_QUERY_HELP)],
        limit: Annotated[int, Field(description=SEARCH_LIMIT_HELP)] = _DEFAULT_SEARCH_LIMIT,
    ) -> CallToolResult:
        """Search one folder with an IMAP query; return one summary line per match."""
        try:
            summaries = await asyncio.to_thread(reader.search, folder, query, limit)
        except (FolderUnknownError, SearchRefusedError) as correction:
            return _one_text(str(correction), failed=True)
        if not summaries:
            return _one_text("(no matching messages)")
        lines = "\n".join(f"[{s.uid}] {s.date} | {s.sender} | {s.subject}" for s in summaries)
        return _one_text(lines)

    @server.tool()
    async def read_email(
        folder: Annotated[str, Field(description=FOLDER_HELP)],
        uid: Annotated[str, Field(description=UID_HELP)],
    ) -> CallToolResult:
        """Read one message in full (headers + plain-text body) by its uid."""
        try:
            detail = await asyncio.to_thread(reader.read, folder, uid)
        except FolderUnknownError as unknown:
            return _one_text(str(unknown), failed=True)
        if detail is None:
            return _one_text(NOT_FOUND.format(uid=uid, folder=folder))
        text = (
            f"From: {detail.sender}\nTo: {detail.recipients}\n"
            f"Date: {detail.date}\nSubject: {detail.subject}\n\n{detail.body}"
        )
        return CallToolResult(
            content=[TextContent(type="text", text=text)], _meta=_sender_source(detail.sender)
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
        async def send_email(  # noqa: PLR0913
            to: str,
            subject: str,
            body: str,
            cc: str = "",
            bcc: str = "",
            html: str = "",
            attachments: Annotated[
                Sequence[EmailAttachment], Field(description=ATTACHMENTS_HELP)
            ] = (),
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
