"""Behaviour of the reader behind the stub gate: what a comment is, and how prost re-spells one.

Every normalization here is a claim about what prost does to a comment on its way into `///`, so
each is asserted on its own rather than only through the whole comparison: an escaped bracket, a
heading marker, a collapsed rule line. `test_stubcheck.py` puts the same three claims against the
real proto and the real committed stub, where they are true or the gate is worthless.

The string rule gets the same treatment. A `//` inside a string literal punctuates nothing, and a
reader that took it for a comment would truncate the real comment on that line and then never
check what it cut off, which is a miss reported as a pass.
"""

import pytest

from protocomments import (
    RULE,
    Comment,
    ProtoReadError,
    normalize,
    proto_comments,
    rust_docs,
    split_comment,
)

HEAD = 'syntax = "proto3";\n\npackage cortex.seam.v1;\n'
ESCAPED_QUOTE = 'option (q) = "say \\" here"; // after the escape'
UNTERMINATED = 'option (q) = "unterminated // still a string'


# ── where the proto body starts ────────────────────────────────────────────────


def test_the_header_above_the_syntax_line_is_not_a_comment() -> None:
    """It attaches to no declaration, so prost copies it nowhere and nothing may expect it."""
    header = "// body.proto is the source of truth.\n// Regenerate with `just proto`.\n"
    assert proto_comments(header + HEAD + "// in the body\n") == [
        Comment(line=6, text=" in the body", leading=True),
    ]


def test_a_trailing_comment_on_the_syntax_line_is_header_too() -> None:
    """The syntax statement generates no item, so a comment on it documents nothing."""
    assert proto_comments('syntax = "proto3"; // proto2 is not offered\n') == []


def test_a_file_with_no_syntax_line_is_refused() -> None:
    """Fail closed: without it the header cannot be told from the body, so neither is read."""
    with pytest.raises(ProtoReadError, match="cannot be told from the body"):
        proto_comments("// orphaned comment\n")


def test_an_empty_file_is_refused_for_the_same_reason() -> None:
    with pytest.raises(ProtoReadError, match="cannot be told from the body"):
        proto_comments("")


def test_a_comment_is_numbered_by_the_whole_file_not_by_the_body() -> None:
    """The number is a pointer a reader opens the proto with, so it counts the skipped header."""
    assert [comment.line for comment in proto_comments(HEAD + "\n\n// here\n")] == [6]


# ── what a comment is ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("// a comment alone on its line", ("", " a comment alone on its line")),
        ("uint32 edge = 1; // longest edge", ("uint32 edge = 1; ", " longest edge")),
        ("uint32 edge = 1;", ("uint32 edge = 1;", None)),
        ("//", ("", "")),
        ("// see https://example.com/spec", ("", " see https://example.com/spec")),
        ('option (url) = "https://e.com";', ('option (url) = "https://e.com";', None)),
        ("option (path) = 'a//b';", ("option (path) = 'a//b';", None)),
        (ESCAPED_QUOTE, ('option (q) = "say \\" here"; ', " after the escape")),
        (UNTERMINATED, (UNTERMINATED, None)),
    ],
)
def test_split_comment_reads_only_a_double_slash_outside_a_string(
    line: str, expected: tuple[str, str | None]
) -> None:
    assert split_comment(1, line) == expected


def test_a_block_comment_is_refused_rather_than_guessed_at() -> None:
    """prost copies these too, in a shape this reader does not know; a skip is a lost check."""
    with pytest.raises(ProtoReadError, match="line 4: block comment"):
        proto_comments(HEAD + "/* a block comment */\n")


def test_a_block_opener_inside_a_line_comment_is_just_text() -> None:
    """The refusal is about code, and the `//` came first, so this is prose about C."""
    assert split_comment(1, "// C spells it /* so */") == ("", " C spells it /* so */")


def test_whether_a_comment_stands_alone_is_recorded() -> None:
    """The two kinds are read by different rules, so the count of each is worth stating."""
    comments = proto_comments(HEAD + "// leading\nuint32 edge = 1; // trailing\n")
    assert [(comment.text, comment.leading) for comment in comments] == [
        (" leading", True),
        (" trailing", False),
    ]


# ── which comments the stub holds two copies of ────────────────────────────────


def _claimed(body: str) -> list[str]:
    """The texts a service claims, which is what the stub is then owed two of."""
    return [comment.text for comment in proto_comments(HEAD + body) if comment.service]


def test_a_comment_inside_a_service_block_is_claimed_by_it() -> None:
    """Tonic writes the service into a client module and a server module and documents both."""
    assert _claimed("service S {\n  // what this rpc does\n  rpc A(X) returns (Y);\n}\n") == [
        " what this rpc does"
    ]


def test_the_banner_standing_directly_above_a_service_is_claimed_too() -> None:
    """It is the service's own leading comment, so it comes out wherever the service does."""
    banner = "// ---\n// S is hosted here.\nservice S {}\n"
    assert _claimed(banner) == [" ---", " S is hosted here."]


def test_a_trailing_comment_on_the_service_line_is_claimed() -> None:
    assert _claimed("service S { // the seam's brain half\n}\n") == [" the seam's brain half"]


def test_a_blank_line_between_the_banner_and_the_service_detaches_it() -> None:
    """protoc reads a detached comment as documenting nothing, and claiming a copy too many

    would be a red on a tree that is perfectly in sync. Fewer claims is the safe direction.
    """
    assert _claimed("// detached\n\nservice S {}\n") == []


def test_a_comment_above_something_that_is_not_a_service_is_not_claimed() -> None:
    assert _claimed("// about a message\nmessage M {\n  uint32 a = 1; // a field\n}\n") == []


def test_a_comment_after_the_service_block_closes_is_not_claimed() -> None:
    """The depth is what closes the claim, so a message following a service is read plainly."""
    assert _claimed("service S {}\n// after it\nmessage M {}\n") == []


def test_a_service_nested_in_no_braces_claims_only_its_own_block() -> None:
    """A brace block opened by anything else is not a service, however deep the comment sits."""
    body = "message M {\n  // inside a message\n}\nservice S {\n  // inside the service\n}\n"
    assert _claimed(body) == [" inside the service"]


# ── what the generated stub says ───────────────────────────────────────────────


def test_doc_lines_are_read_whatever_their_indent() -> None:
    stub = "/// at the top\nmod inner {\n        /// deeply nested\n}\n"
    assert rust_docs(stub) == [" at the top", " deeply nested"]


def test_an_ordinary_comment_in_the_stub_is_not_a_doc_comment() -> None:
    """prost's own banner documents the file rather than an item, and copies no proto prose."""
    assert rust_docs("// This file is @generated by prost-build.\n//! inner doc\n") == []


def test_an_empty_doc_line_says_nothing() -> None:
    """prost writes one between a leading block and what follows, and the proto writes it too."""
    assert rust_docs("///\n") == [""]


# ── the three re-spellings, one at a time ──────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (" clamped to \\[0.0, 1.0\\]", "clamped to [0.0, 1.0]"),
        (" clamped to [0.0, 1.0]", "clamped to [0.0, 1.0]"),
        (" ## BodyService is hosted by the body", "BodyService is hosted by the body"),
        (" #### deeper", "deeper"),
        (" ---------------------------------------", RULE),
        (" ---", RULE),
        ("-", RULE),
        (" read-only email over IMAP", "read-only email over IMAP"),
        ("", ""),
    ],
)
def test_normalize_reduces_both_spellings_to_one(text: str, expected: str) -> None:
    assert normalize(text) == expected
