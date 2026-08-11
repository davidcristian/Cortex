"""Behavior tests for the email FastMCP server: the tools call the reader, in-process.

Each tool returns a single readable string; these assert on that text (what a text client,
and thus the model, actually receives), not on FastMCP's structured side-channel.
"""
# The autouse env-isolation fixture below is invoked by pytest, not statically
# referenced. Pyright cannot see that. (Same class as server.py's decorator handlers.)
# pyright: reportUnusedFunction=false

from collections.abc import Sequence
from typing import cast

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

import cortex_email.server as server_module
from cortex_email import (
    EmailAttachment,
    EmailDraft,
    EmailReader,
    RawEmail,
    SmtpSender,
    build_server,
    main,
)
from cortex_email.values import MAX_ATTACHMENT_CHARS, MAX_ATTACHMENTS, MAX_FILENAME_CHARS

_SIMPLE = (
    b"From: A <a@x.com>\r\nSubject: Hi\r\n"
    b"Date: Fri, 03 Jul 2026 12:00:00 +0000\r\n\r\nbody text\r\n"
)

# A message with no From header: read_email declares no sender source for it.
_NO_SENDER = b"Subject: Hi\r\nDate: Fri, 03 Jul 2026 12:00:00 +0000\r\n\r\nbody text\r\n"


_SMTP_ENV = (
    "CORTEX_EMAIL_SEND_ENABLED",
    "CORTEX_EMAIL_SMTP_ENABLED",
    "CORTEX_EMAIL_SMTP_USER",
    "CORTEX_EMAIL_SMTP_PASSWORD",
)


@pytest.fixture(autouse=True)
def _clean_smtp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Isolate the send-path env so a sourced ~/.cortex/email.env can't make `main()` wire a
    # sender in the read-only-default test; tests that need it set the vars after this runs.
    for name in _SMTP_ENV:
        monkeypatch.delenv(name, raising=False)


class FakeMailbox:
    def __init__(
        self,
        *,
        folders: Sequence[str] = (),
        found: Sequence[RawEmail] = (),
        one: RawEmail | None = None,
    ) -> None:
        self._folders = folders
        self._found = found
        self._one = one

    def list_folders(self) -> Sequence[str]:
        return self._folders

    def search(self, folder: str, query: str, limit: int) -> Sequence[RawEmail]:
        del folder, query, limit
        return self._found

    def fetch(self, folder: str, uid: str) -> RawEmail | None:
        del folder, uid
        return self._one


async def _text(server: FastMCP, name: str, args: dict[str, object]) -> str:
    # read_email returns a CallToolResult (it declares a source, below); the string-returning tools
    # come back as FastMCP's (unstructured, structured) pair. Both reduce to the readable text.
    result: object = await server.call_tool(name, args)
    if isinstance(result, CallToolResult):
        blocks: Sequence[object] = result.content
    else:
        blocks = cast("tuple[Sequence[TextContent], object]", result)[0]
    return "".join(block.text for block in blocks if isinstance(block, TextContent))


async def test_list_folders_tool() -> None:
    server = build_server(EmailReader(FakeMailbox(folders=["INBOX", "Archive"])))
    assert await _text(server, "list_folders", {}) == "INBOX\nArchive"


async def test_search_emails_tool_formats_one_line_per_hit() -> None:
    server = build_server(EmailReader(FakeMailbox(found=[RawEmail("7", _SIMPLE)])))
    text = await _text(server, "search_emails", {"folder": "INBOX", "query": "ALL"})
    assert text == "[7] Fri, 03 Jul 2026 12:00:00 +0000 | A <a@x.com> | Hi"


async def test_search_emails_tool_reports_no_matches() -> None:
    server = build_server(EmailReader(FakeMailbox(found=[])))
    assert await _text(server, "search_emails", {"folder": "INBOX", "query": "ALL"}) == (
        "(no matching messages)"
    )


async def test_read_email_tool_returns_formatted_message() -> None:
    server = build_server(EmailReader(FakeMailbox(one=RawEmail("7", _SIMPLE))))
    text = await _text(server, "read_email", {"folder": "INBOX", "uid": "7"})
    assert text.startswith("From: A <a@x.com>")
    assert "Subject: Hi" in text
    assert text.endswith("\n\nbody text")


async def test_read_email_tool_reports_not_found() -> None:
    server = build_server(EmailReader(FakeMailbox(one=None)))
    text = await _text(server, "read_email", {"folder": "INBOX", "uid": "999"})
    assert text == "message 999 not found in INBOX"


async def test_read_email_declares_the_message_sender_as_a_source() -> None:
    # The producer half of the sidecar declaration channel (ADR-0027): the sender rides in the
    # result `_meta`, beside (never inside) the readable string the model consumes. The brain's
    # tool registry reads this key and, being the trust gate, admits it only as a claimed source.
    server = build_server(EmailReader(FakeMailbox(one=RawEmail("7", _SIMPLE))))
    result = cast(
        "CallToolResult", await server.call_tool("read_email", {"folder": "x", "uid": "7"})
    )
    assert result.meta == {"cortex/source": {"kind": "sender", "value": "A <a@x.com>"}}
    text = "".join(b.text for b in result.content if isinstance(b, TextContent))
    assert text.startswith("From: A <a@x.com>")  # the declaration left the content untouched


async def test_read_email_declares_no_source_without_a_sender_or_when_not_found() -> None:
    # A message with no From header, and a missing message, both declare nothing rather than an
    # empty sender: the wire carries a source only when there is one.
    no_sender = build_server(EmailReader(FakeMailbox(one=RawEmail("8", _NO_SENDER))))
    found = cast(
        "CallToolResult", await no_sender.call_tool("read_email", {"folder": "x", "uid": "8"})
    )
    assert found.meta is None
    missing_server = build_server(EmailReader(FakeMailbox(one=None)))
    missing = cast(
        "CallToolResult", await missing_server.call_tool("read_email", {"folder": "x", "uid": "9"})
    )
    assert missing.meta is None


class FakeSender:
    """Records sends and returns the readable confirmation line (the SmtpSender contract)."""

    def __init__(self) -> None:
        self.sent: list[EmailDraft] = []

    def send(self, draft: EmailDraft) -> str:
        self.sent.append(draft)
        return f"email sent to {draft.to}"


async def _tool_names(server: FastMCP) -> set[str]:
    return {tool.name for tool in await server.list_tools()}


async def test_without_a_sender_only_the_read_tools_register() -> None:
    # The Slice 6 read-only-by-construction property, preserved by default (ADR-0022).
    server = build_server(EmailReader(FakeMailbox()))
    assert await _tool_names(server) == {"list_folders", "search_emails", "read_email"}


async def test_with_a_sender_send_email_registers_with_write_annotations() -> None:
    server = build_server(EmailReader(FakeMailbox()), FakeSender())
    tools = {tool.name: tool for tool in await server.list_tools()}
    assert set(tools) == {"list_folders", "search_emails", "read_email", "send_email"}
    annotations = tools["send_email"].annotations
    assert annotations is not None
    # Advisory MCP metadata (never authority, because the brain-side overlay gates it).
    assert annotations.readOnlyHint is False
    assert annotations.destructiveHint is True
    assert annotations.openWorldHint is True


async def test_send_email_tool_sends_and_reports() -> None:
    sender = FakeSender()
    server = build_server(EmailReader(FakeMailbox()), sender)
    text = await _text(
        server, "send_email", {"to": "you@example.com", "subject": "Hi", "body": "hello"}
    )
    assert text == "email sent to you@example.com"
    (draft,) = sender.sent
    assert (draft.to, draft.subject, draft.body) == ("you@example.com", "Hi", "hello")
    assert (draft.cc, draft.bcc, draft.html) == ("", "", "")  # omitted shapes default empty
    assert draft.attachments == ()


async def test_send_email_tool_forwards_cc_bcc_and_html() -> None:
    sender = FakeSender()
    server = build_server(EmailReader(FakeMailbox()), sender)
    text = await _text(
        server,
        "send_email",
        {
            "to": "you@example.com",
            "subject": "Hi",
            "body": "hello",
            "cc": "c@example.com",
            "bcc": "b@example.com",
            "html": "<p>hi</p>",
        },
    )
    assert text == "email sent to you@example.com"
    (draft,) = sender.sent
    assert (draft.cc, draft.bcc, draft.html) == ("c@example.com", "b@example.com", "<p>hi</p>")


async def test_send_email_tool_forwards_attachments_as_values() -> None:
    # The nested array-of-objects argument is the first of its shape in the repo: what this
    # pins is that the JSON the model writes arrives as EmailAttachment values on the draft.
    sender = FakeSender()
    server = build_server(EmailReader(FakeMailbox()), sender)
    text = await _text(
        server,
        "send_email",
        {
            "to": "you@example.com",
            "subject": "Hi",
            "body": "see attached",
            "attachments": [
                {"filename": "notes.md", "content": "# Notes", "subtype": "markdown"},
                {"filename": "log.txt", "content": "line one"},  # subtype defaults to plain
            ],
        },
    )
    assert text == "email sent to you@example.com"
    (draft,) = sender.sent
    assert draft.attachments == (
        EmailAttachment("notes.md", "# Notes", "markdown"),
        EmailAttachment("log.txt", "line one"),
    )


async def test_the_send_tool_advertises_the_attachment_shape() -> None:
    # The model can only fill a shape it is told about, and this schema is generated rather
    # than written, so assert the nested object reaches the advertised parameters.
    server = build_server(EmailReader(FakeMailbox()), FakeSender())
    (tool,) = [t for t in await server.list_tools() if t.name == "send_email"]
    attachments = tool.inputSchema["properties"]["attachments"]
    assert attachments["type"] == "array"
    definition = tool.inputSchema["$defs"]["EmailAttachment"]
    assert set(definition["required"]) == {"filename", "content"}
    assert definition["properties"]["subtype"]["default"] == "plain"


async def test_every_attachment_field_says_what_it_is_for() -> None:
    # The shape alone leaves three guesses, and each wrong one is refused inside the sidecar
    # *after* the user approved the card, so the descriptions name the fact that settles it:
    # the filename's own ceiling, that `content` is the file rather than a path to one, and
    # that `subtype` is the bare token rather than a whole MIME type.
    server = build_server(EmailReader(FakeMailbox()), FakeSender())
    (tool,) = [t for t in await server.list_tools() if t.name == "send_email"]
    fields = tool.inputSchema["$defs"]["EmailAttachment"]["properties"]
    assert set(fields) == {"filename", "content", "subtype"}  # every one of them, below
    # The subtype fact is the phrase that *locates* the token, not the bare "text/": the
    # description also warns off "text/markdown", so matching "text/" alone would survive
    # deleting the sentence that says what to write, which is a check that cannot fail.
    for name, fact in (
        ("filename", str(MAX_FILENAME_CHARS)),
        ("content", "disk"),
        ("subtype", "after 'text/'"),
    ):
        assert fact in fields[name]["description"]


async def test_the_attachments_array_names_the_two_bounds_it_is_refused_against() -> None:
    # Neither bound belongs to a field: one counts the entries and one sums their content, so
    # they ride the array itself, which had no description at all. Both are spelled from the
    # constants SmtpSender refuses against, never restated.
    server = build_server(EmailReader(FakeMailbox()), FakeSender())
    (tool,) = [t for t in await server.list_tools() if t.name == "send_email"]
    described = tool.inputSchema["properties"]["attachments"]["description"]
    assert str(MAX_ATTACHMENTS) in described
    assert str(MAX_ATTACHMENT_CHARS) in described


def test_main_builds_the_server_and_runs_streamable_http(monkeypatch: pytest.MonkeyPatch) -> None:
    transports: list[str] = []
    senders: list[object] = []

    def fake_run(_self: FastMCP, transport: str) -> None:
        transports.append(transport)

    def spy_build(reader: EmailReader, sender: object = None) -> FastMCP:
        senders.append(sender)
        return build_server(reader, None)

    monkeypatch.setattr(FastMCP, "run", fake_run)
    monkeypatch.setattr(server_module, "build_server", spy_build)
    main()
    assert transports == ["streamable-http"]
    assert senders == [None]  # send disabled by default: the read-only server


def test_main_wires_a_sender_when_send_is_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_EMAIL_SEND_ENABLED", "true")
    monkeypatch.setenv("CORTEX_EMAIL_SMTP_USER", "me@example.com")
    monkeypatch.setenv("CORTEX_EMAIL_SMTP_PASSWORD", "pw")
    transports: list[str] = []
    senders: list[object] = []

    def fake_run(_self: FastMCP, transport: str) -> None:
        transports.append(transport)

    def spy_build(reader: EmailReader, sender: object = None) -> FastMCP:
        senders.append(sender)
        return build_server(reader, None)

    monkeypatch.setattr(FastMCP, "run", fake_run)
    monkeypatch.setattr(server_module, "build_server", spy_build)
    main()
    assert transports == ["streamable-http"]
    (sender,) = senders
    assert isinstance(sender, SmtpSender)
