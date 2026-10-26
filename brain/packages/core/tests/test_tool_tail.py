from collections.abc import Mapping, Sequence
from typing import Any

from cortex_core import LastLinesToolRegistry, ToolCall, ToolResult, ToolSpec

_SPEC = ToolSpec(name="read_text_file", description="read a file", parameters={})


class _TailServer:
    """Reads ``tail`` lines of ``text`` the way the reference filesystem server does."""

    def __init__(self, text: str, *, is_error: bool = False) -> None:
        self._text = text
        self._is_error = is_error
        self.sent: list[Mapping[str, Any]] = []

    async def describe_tools(self) -> Sequence[ToolSpec]:
        return (_SPEC,)

    async def invoke(self, call: ToolCall) -> ToolResult:
        self.sent.append(call.arguments)
        count = call.arguments.get("tail")
        lines = self._text.split("\n")
        text = "\n".join(lines[-count:]) if isinstance(count, int) else self._text
        return ToolResult(call_id=call.id, content=text, is_error=self._is_error)


def _read(**arguments: object) -> ToolCall:
    return ToolCall(id="c1", name="read_text_file", arguments={"path": "/a.log", **arguments})


async def _tail(text: str, call: ToolCall) -> tuple[str, list[Mapping[str, Any]]]:
    server = _TailServer(text)
    registry = LastLinesToolRegistry(server, tools=("read_text_file",))
    return (await registry.invoke(call)).content, server.sent


async def test_the_last_line_of_a_file_ending_in_a_newline_is_its_text() -> None:
    content, sent = await _tail("first\nsecond\nthe last line\n", _read(tail=1))
    assert content == "the last line"
    assert sent == [{"path": "/a.log", "tail": 2}]


async def test_two_last_lines_are_the_two_lines_before_the_final_newline() -> None:
    content, _ = await _tail("first\nsecond\nthe last line\n", _read(tail=2))
    assert content == "second\nthe last line"


async def test_a_file_with_no_final_newline_still_gives_its_last_line() -> None:
    content, _ = await _tail("first\nsecond\nthe last line", _read(tail=1))
    assert content == "the last line"


async def test_a_file_shorter_than_the_tail_is_returned_whole() -> None:
    content, _ = await _tail("first\nsecond\n", _read(tail=5))
    assert content == "first\nsecond"


async def test_a_file_whose_last_line_is_really_empty_says_so() -> None:
    content, _ = await _tail("first\n\n", _read(tail=1))
    assert content == ""


async def test_a_read_without_a_tail_is_passed_on_unchanged() -> None:
    content, sent = await _tail("first\nsecond\n", _read(head=1))
    assert content == "first\nsecond\n"
    assert sent == [{"path": "/a.log", "head": 1}]


async def test_a_tail_that_is_not_a_positive_count_is_passed_on_unchanged() -> None:
    for tail in (True, 0, -1, "1"):
        _, sent = await _tail("first\nsecond\n", _read(tail=tail))
        assert sent == [{"path": "/a.log", "tail": tail}]


async def test_a_tool_not_named_is_passed_on_unchanged() -> None:
    server = _TailServer("first\nsecond\n")
    registry = LastLinesToolRegistry(server, tools=("read_file",))
    result = await registry.invoke(_read(tail=1))
    assert server.sent == [{"path": "/a.log", "tail": 1}]
    assert result.content == ""


async def test_a_failed_read_is_returned_as_the_server_wrote_it() -> None:
    server = _TailServer("access denied\n", is_error=True)
    registry = LastLinesToolRegistry(server, tools=("read_text_file",))
    result = await registry.invoke(_read(tail=1))
    assert result == ToolResult(call_id="c1", content="access denied\n", is_error=True)


async def test_the_tools_listed_are_the_inner_registrys() -> None:
    registry = LastLinesToolRegistry(_TailServer(""), tools=("read_text_file",))
    assert await registry.describe_tools() == (_SPEC,)
