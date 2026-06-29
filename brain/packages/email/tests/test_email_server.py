"""Behavior tests for the email FastMCP server: the tools call the reader, in-process.

Each tool returns a single readable string; these assert on that text (what a text client,
and thus the model, actually receives), not on FastMCP's structured side-channel.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, cast

import pytest
from mcp.server.fastmcp import FastMCP

from cortex_email import EmailReader, RawEmail, build_server, main

if TYPE_CHECKING:
    from mcp.types import TextContent

_SIMPLE = (
    b"From: A <a@x.com>\r\nSubject: Hi\r\n"
    b"Date: Fri, 03 Jul 2026 12:00:00 +0000\r\n\r\nbody text\r\n"
)


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
    result = await server.call_tool(name, args)
    blocks = cast("tuple[Sequence[TextContent], object]", result)[0]
    return "".join(block.text for block in blocks)


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


def test_main_builds_the_server_and_runs_streamable_http(monkeypatch: pytest.MonkeyPatch) -> None:
    transports: list[str] = []

    def fake_run(_self: FastMCP, transport: str) -> None:
        transports.append(transport)

    monkeypatch.setattr(FastMCP, "run", fake_run)
    main()
    assert transports == ["streamable-http"]
