"""Behavior tests for the email FastMCP server: the tools call the reader, in-process."""

from collections.abc import Sequence
from typing import cast

import pytest
from mcp.server.fastmcp import FastMCP

from cortex_email import EmailReader, RawEmail, build_server, main

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


async def _structured(server: FastMCP, name: str, args: dict[str, object]) -> dict[str, object]:
    result = await server.call_tool(name, args)
    return cast("tuple[object, dict[str, object]]", result)[1]


async def test_list_folders_tool() -> None:
    server = build_server(EmailReader(FakeMailbox(folders=["INBOX", "Archive"])))
    assert await _structured(server, "list_folders", {}) == {"result": ["INBOX", "Archive"]}


async def test_search_emails_tool() -> None:
    server = build_server(EmailReader(FakeMailbox(found=[RawEmail("7", _SIMPLE)])))
    structured = await _structured(server, "search_emails", {"folder": "INBOX", "query": "ALL"})
    assert structured == {
        "result": [
            {
                "uid": "7",
                "sender": "A <a@x.com>",
                "subject": "Hi",
                "date": "Fri, 03 Jul 2026 12:00:00 +0000",
            }
        ]
    }


async def test_read_email_tool_returns_detail() -> None:
    server = build_server(EmailReader(FakeMailbox(one=RawEmail("7", _SIMPLE))))
    structured = await _structured(server, "read_email", {"folder": "INBOX", "uid": "7"})
    assert structured["subject"] == "Hi"
    assert structured["body"] == "body text"


async def test_read_email_tool_reports_not_found() -> None:
    server = build_server(EmailReader(FakeMailbox(one=None)))
    structured = await _structured(server, "read_email", {"folder": "INBOX", "uid": "999"})
    assert structured == {"uid": "999", "error": "message not found"}


def test_main_builds_the_server_and_runs_streamable_http(monkeypatch: pytest.MonkeyPatch) -> None:
    transports: list[str] = []

    def fake_run(_self: FastMCP, transport: str) -> None:
        transports.append(transport)

    monkeypatch.setattr(FastMCP, "run", fake_run)
    main()
    assert transports == ["streamable-http"]
