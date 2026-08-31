"""Behavior tests for the email FastMCP server: the tools call the reader, in-process.

Each tool answers with a single readable text block; these assert on that text (what a text
client, and thus the model, actually receives), not on FastMCP's structured side-channel. Two
of them wrap it in a `CallToolResult` of their own, so the assertions that are about the
wrapping (a declared source, a refused query's `isError`) read the result rather than `_text`.
"""
# The autouse env-isolation fixture below is invoked by pytest, not statically
# referenced. Pyright cannot see that. (Same class as server.py's decorator handlers.)
# pyright: reportUnusedFunction=false

from collections.abc import Sequence
from typing import cast

import pytest
from mailbox_fake import FakeMailbox
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import CallToolResult, TextContent

import cortex_email.server as server_module
from cortex_email import (
    EmailAttachment,
    EmailDraft,
    EmailReader,
    MailboxError,
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


async def _text(server: FastMCP, name: str, args: dict[str, object]) -> str:
    # search_emails and read_email return a CallToolResult (one marks a refusal, the other
    # declares a source, both below); the string-returning tools come back as FastMCP's
    # (unstructured, structured) pair. Both reduce to the readable text.
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


async def test_search_emails_tool_hands_a_refusal_to_the_model_in_its_own_words() -> None:
    # On a refused query the model reads the port's own sentence, whole, with nothing of the IMAP
    # library in it and no FastMCP "Error executing tool search_emails:" in front, which is what a
    # tool that let the exception out would have produced. `isError` still marks the call failed
    # for the audit trail.
    mailbox = FakeMailbox()
    mailbox.refuse()
    server = build_server(EmailReader(mailbox))
    result = cast(
        "CallToolResult",
        await server.call_tool(
            "search_emails", {"folder": "INBOX", "query": "from:someone@example.com"}
        ),
    )
    assert result.isError is True
    text = "".join(b.text for b in result.content if isinstance(b, TextContent))
    assert text == (
        "The mail server refused this search as malformed, so nothing was searched and no "
        "message was read. The query is raw IMAP SEARCH criteria, and the query field's own "
        "description spells that dialect out in full, criterion by criterion: write the search "
        "again from it rather than sending this one a second time, which is refused again. The "
        "refused query was 'from:someone@example.com'"
    )


async def test_both_folder_taking_tools_answer_an_unknown_folder_in_the_same_words() -> None:
    # The folder is the guess both read tools invite, so both answer it identically: the port's
    # own sentence, whole, with nothing of the IMAP library in it, no FastMCP "Error executing
    # tool ..." in front, and the one call that fixes it named. `read_email` fails on the folder
    # before it looks at a uid, so it must not say "message not found" instead, which would send
    # a model hunting through a folder that is not there. `isError` marks both failed for the
    # audit trail, and a failed read declares no source.
    expected = (
        "The mail server has no folder by that name, so nothing was searched and no message was "
        "read. Folder names are matched exactly and are never normalised or guessed at: call "
        "list_folders and use a name spelled exactly as that list returns it, rather than trying "
        "another name that looks likely. The folder name that was refused was 'Receipts'"
    )
    server = build_server(EmailReader(FakeMailbox(one=RawEmail("7", _SIMPLE))))
    searched = cast(
        "CallToolResult",
        await server.call_tool("search_emails", {"folder": "Receipts", "query": "ALL"}),
    )
    read = cast(
        "CallToolResult", await server.call_tool("read_email", {"folder": "Receipts", "uid": "7"})
    )
    for result in (searched, read):
        assert result.isError is True
        assert "".join(b.text for b in result.content if isinstance(b, TextContent)) == expected
    assert read.meta is None


async def test_a_mailbox_that_cannot_answer_is_still_a_tool_failure() -> None:
    # A mailbox that could not answer at all is deliberately not caught: that is a tool failure,
    # and FastMCP restating it as an execution error describes it correctly. Only a refused query
    # is an answer the tool gives in its own words. FastMCP raises this `ToolError` and the
    # low-level server renders `str(err)` as the isError text a client reads, so the sentence
    # asserted here is the one that reaches the model, prefix and all.
    class DownMailbox(FakeMailbox):
        def search(self, folder: str, query: str, limit: int) -> Sequence[RawEmail]:
            del folder, query, limit
            msg = "the mailbox could not run that search: connection refused"
            raise MailboxError(msg)

    server = build_server(EmailReader(DownMailbox()))
    with pytest.raises(ToolError) as raised:
        await server.call_tool("search_emails", {"folder": "INBOX", "query": "ALL"})
    assert str(raised.value) == (
        "Error executing tool search_emails: the mailbox could not run that search: "
        "connection refused"
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
        "CallToolResult", await server.call_tool("read_email", {"folder": "INBOX", "uid": "7"})
    )
    assert result.meta == {"cortex/source": {"kind": "sender", "value": "A <a@x.com>"}}
    text = "".join(b.text for b in result.content if isinstance(b, TextContent))
    assert text.startswith("From: A <a@x.com>")  # the declaration left the content untouched


async def test_read_email_declares_no_source_without_a_sender_or_when_not_found() -> None:
    # A message with no From header, and a missing message, both declare nothing rather than an
    # empty sender: the wire carries a source only when there is one.
    no_sender = build_server(EmailReader(FakeMailbox(one=RawEmail("8", _NO_SENDER))))
    found = cast(
        "CallToolResult", await no_sender.call_tool("read_email", {"folder": "INBOX", "uid": "8"})
    )
    assert found.meta is None
    missing_server = build_server(EmailReader(FakeMailbox(one=None)))
    missing = cast(
        "CallToolResult",
        await missing_server.call_tool("read_email", {"folder": "INBOX", "uid": "9"}),
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
    # Building without a sender registers no write tool at all, which is the read-only-by-
    # construction default the send path preserved (ADR-0022).
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


async def test_the_search_tool_names_the_dialect_its_query_is_written_in() -> None:
    # `query` reaches the IMAP server unaltered, so a model writing the `key:value` of a mail
    # client spends a whole dispatch on a parse error it cannot repair. Each phrase below is the
    # one that *locates* a fact, never a substring that would survive deleting the sentence
    # carrying it: the quoted-argument form, a date in the only shape the server parses, the two
    # composition words, and the refusal that names the client syntax by example.
    server = build_server(EmailReader(FakeMailbox()))
    (tool,) = [t for t in await server.list_tools() if t.name == "search_emails"]
    described = tool.inputSchema["properties"]["query"]["description"]
    for fact in ('FROM "someone@example.com"', "01-Jan-2026", "OR takes", "NOT negates"):
        assert fact in described
    assert "from:someone@example.com is refused" in described


async def test_the_read_tools_say_where_a_folder_name_comes_from() -> None:
    # A folder name is taken verbatim, so an invented one is an error rather than an empty
    # result. Both tools that take a folder say so, from one constant, which is what stops the
    # two descriptions drifting apart.
    server = build_server(EmailReader(FakeMailbox()))
    tools = {t.name: t for t in await server.list_tools()}
    for name in ("search_emails", "read_email"):
        assert (
            "list_folders returned it"
            in tools[name].inputSchema["properties"]["folder"]["description"]
        )


async def test_the_search_limit_says_which_matches_it_keeps() -> None:
    # A limit that means "the oldest N" without saying so misleads the model, so the description
    # says it: the fetch is ascending-uid, and raising the limit is not how a recent message is
    # found.
    server = build_server(EmailReader(FakeMailbox()))
    (tool,) = [t for t in await server.list_tools() if t.name == "search_emails"]
    limit = tool.inputSchema["properties"]["limit"]
    assert limit["default"] == 20
    assert "not the same as the newest" in limit["description"]


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
