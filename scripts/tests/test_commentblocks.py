import pytest

from commentblocks import (
    Block,
    CommentLine,
    Comments,
    Docstring,
    SourceError,
    comment_blocks,
    counts,
    decorated_docstrings,
    hash_comments,
    is_directive,
    module_docstring,
    python_comments,
    python_docstrings,
)

DECORATED = '''"""Module."""


@server.tool()
async def first() -> None:
    """First tool."""


@server.tool
def second() -> None:
    """Second tool."""


@server.tool()
def third() -> None:
    return None


@other()
def fourth() -> None:
    """Not a tool."""


@registry[0]
def fifth() -> None:
    """Also not a tool."""
'''

PYTHON = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
x = 0

# one
# two

# three
x = 1  # trailing
# four
#
# pragma: no cover -- reason
def f():
    return (
        # inside brackets
        1
    )
"""


def test_python_comments_are_found_with_their_lines() -> None:
    comments = python_comments(PYTHON)
    assert comments.lines[4:7] == [
        CommentLine(8, " three"),
        CommentLine(9, " trailing"),
        CommentLine(10, " four"),
    ]
    assert comments.code == frozenset({3, 9, 13, 14, 16, 17})


def test_blocks_end_at_code_but_not_at_blank_lines() -> None:
    assert comment_blocks(python_comments(PYTHON)) == [
        Block(first=1, last=2, lines=0),
        Block(first=5, last=8, lines=3),
        Block(first=10, last=12, lines=1),
        Block(first=15, last=15, lines=1),
    ]


def test_a_block_after_the_last_code_line_is_kept() -> None:
    assert comment_blocks(python_comments("x = 1\n# a\n# b\n")) == [Block(2, 3, 2)]


def test_a_file_with_no_comment_has_no_block() -> None:
    assert comment_blocks(python_comments("x = 1\n")) == []


def test_python_that_cannot_be_tokenized_is_an_error() -> None:
    with pytest.raises(SourceError):
        python_comments("x = (\n")


@pytest.mark.parametrize(
    ("line", "text", "expected"),
    [
        (1, "!/bin/sh", True),
        (2, "!/bin/sh", False),
        (2, " -*- coding: utf-8 -*-", True),
        (3, " coding: utf-8", False),
        (5, " noqa: E501", True),
        (5, " type: ignore[misc]", True),
        (5, " pragma: no cover -- reason", True),
        (5, " pyright: basic", True),
        (5, " fmt: off", True),
        (5, " ruff: noqa", True),
        (5, " nosec", True),
        (5, " @ts-expect-error missing types", True),
        (5, " eslint-disable-next-line", True),
        (5, ' <reference types="vite/client" />', True),
        (1, " syntax=docker/dockerfile:1", True),
        (5, " The reason noqa is needed here", False),
        (5, " pyright's check is off here", False),
    ],
)
def test_directives_are_recognized(line: int, text: str, expected: bool) -> None:  # noqa: FBT001
    assert is_directive(CommentLine(line, text)) is expected


@pytest.mark.parametrize(
    ("text", "expected"), [(" words", True), ("", False), ("   ", False), (" noqa", False)]
)
def test_only_text_that_is_not_a_directive_counts(text: str, expected: bool) -> None:  # noqa: FBT001
    assert counts(CommentLine(5, text)) is expected


def test_hash_comments_skip_quotes_and_need_whitespace_before_the_marker() -> None:
    text = "key: \"#no\" # yes\nurl: a#b\n  # alone\n'it' # after\nplain\n\n# last"
    assert hash_comments(text) == Comments(
        lines=[
            CommentLine(1, " yes"),
            CommentLine(3, " alone"),
            CommentLine(4, " after"),
            CommentLine(7, " last"),
        ],
        code=frozenset({1, 2, 4, 5}),
    )


def test_hash_comments_take_another_marker() -> None:
    text = "SELECT 1; -- note\r\n-- alone\n-- more\n"
    assert hash_comments(text, "--").lines == [
        CommentLine(1, " note"),
        CommentLine(2, " alone"),
        CommentLine(3, " more"),
    ]


DOCSTRINGS = '''"""Module line.

Second paragraph.
"""


class A:
    r"""Class."""

    def f(self):
        """
        One.
        Two.
        Three.
        Four.
        """

    async def g(self): """Inline."""; x = 1

    def h(self):
        return "not a docstring"

    def i(self):
        1

    def j(self):
        call()


def é(): """doc"""
'''


WORDS = ("One", "Two", "Three", "Four")


def test_docstrings_are_found_in_line_order_without_their_quotes() -> None:
    assert python_docstrings(DOCSTRINGS) == [
        Docstring(1, 4, ("Module line.", "", "Second paragraph.", "")),
        Docstring(8, 8, ("Class.",)),
        Docstring(11, 16, ("", *(f"        {word}." for word in WORDS), "        ")),
        Docstring(18, 18, ("Inline.",)),
        Docstring(30, 30, ("doc",)),
    ]


def test_a_docstring_counts_only_lines_that_hold_text() -> None:
    assert [found.lines for found in python_docstrings(DOCSTRINGS)] == [2, 1, 4, 1, 1]


def test_an_empty_module_has_no_docstring() -> None:
    assert python_docstrings("") == []


def test_python_that_cannot_be_parsed_is_an_error() -> None:
    with pytest.raises(SourceError):
        python_docstrings("def f(:\n")


def test_the_module_docstring_is_found_on_its_own() -> None:
    assert module_docstring(DECORATED) == [Docstring(1, 1, ("Module.",))]


def test_a_module_without_a_docstring_has_none() -> None:
    assert module_docstring('def f():\n    """A function, not the module."""\n') == []


def test_only_functions_written_with_the_decorator_are_found() -> None:
    assert decorated_docstrings(DECORATED, "server.tool") == [
        Docstring(6, 6, ("First tool.",)),
        Docstring(11, 11, ("Second tool.",)),
    ]


def test_a_decorator_no_file_uses_finds_nothing() -> None:
    assert decorated_docstrings(DECORATED, "server.prompt") == []


def test_finding_a_module_docstring_reports_source_that_cannot_be_parsed() -> None:
    with pytest.raises(SourceError):
        module_docstring("def f(:\n")


def test_finding_decorated_docstrings_reports_source_that_cannot_be_parsed() -> None:
    with pytest.raises(SourceError):
        decorated_docstrings("def f(:\n", "server.tool")
