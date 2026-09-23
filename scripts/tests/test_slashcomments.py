import pytest

from commentblocks import Block, CommentLine, comment_blocks
from slashcomments import (
    CSS,
    PROTO,
    RUST,
    SYNTAXES,
    TYPESCRIPT,
    Syntax,
    slash_comments,
    slash_strings,
)


def _texts(text: str, syntax: Syntax) -> list[tuple[int, str]]:
    return [(comment.line, comment.text) for comment in slash_comments(text, syntax).lines]


def test_every_language_has_a_syntax() -> None:
    assert SYNTAXES == {
        ".rs": RUST,
        ".ts": TYPESCRIPT,
        ".tsx": TYPESCRIPT,
        ".css": CSS,
        ".proto": PROTO,
    }


def test_line_comments_lose_their_markers() -> None:
    text = "// plain\n/// doc\n//! inner\nx(); // trailing"
    assert _texts(text, RUST) == [(1, " plain"), (2, " doc"), (3, " inner"), (4, " trailing")]


def test_a_block_comment_loses_its_delimiters_and_decoration() -> None:
    text = "/**\n * One.\n *\n * Two.\n */\n/*! inner */\n/**/\n/***/"
    assert _texts(text, TYPESCRIPT) == [
        (1, ""),
        (2, " One."),
        (3, ""),
        (4, " Two."),
        (5, ""),
        (6, " inner"),
        (7, ""),
        (8, ""),
    ]


def test_two_comments_on_one_line_are_joined() -> None:
    assert _texts("/* a */ x /* b */", TYPESCRIPT) == [(1, " a  b")]


def test_the_lines_of_a_multiline_block_comment_are_not_code() -> None:
    text = "{/* one\n  two\n  three\n  four */}\nx"
    comments = slash_comments(text, TYPESCRIPT)
    assert comments.code == frozenset({5})
    assert comment_blocks(comments) == [Block(first=1, last=4, lines=4)]


def test_a_trailing_comment_is_not_part_of_a_block() -> None:
    comments = slash_comments("x(); /* a */\n// b\ny();", RUST)
    assert comments.code == frozenset({1, 3})
    assert comment_blocks(comments) == [Block(first=2, last=2, lines=1)]


def test_rust_block_comments_nest() -> None:
    assert _texts("/* a /* b */ c */ x\n// d", RUST) == [(1, " a /* b */ c"), (2, " d")]


def test_other_block_comments_do_not_nest() -> None:
    assert _texts("/* a /* b */ c */", TYPESCRIPT) == [(1, " a /* b")]


def test_an_unclosed_block_comment_runs_to_the_end() -> None:
    assert _texts("x\n/* a\nb", PROTO) == [(2, " a"), (3, "b")]


@pytest.mark.parametrize(
    "line",
    [
        'let s = "http://x /* y */";',
        'let s = "a \\" // b";',
        'let s = r#"a "// b" c"#;',
        'let s = br"//";',
        "let c = '\"'; let d = '\\'';",
        "let c = '\\u{2014}'; let s = \"//\";",
    ],
)
def test_rust_literals_hide_comment_markers(line: str) -> None:
    assert _texts(line, RUST) == []


def test_a_char_literal_holding_a_quote_does_not_open_a_string() -> None:
    assert _texts('let c = \'"\'; let s = "// no"; // real', RUST) == [(1, " real")]


def test_a_lifetime_is_not_a_char_literal() -> None:
    assert _texts("fn f<'a>(x: &'a str) {} // real", RUST) == [(1, " real")]


def test_a_rust_string_may_span_lines() -> None:
    comments = slash_comments('let s = "one\n// two\n";\n// three', RUST)
    assert (comments.lines, comments.code) == ([CommentLine(4, " three")], frozenset({1, 2, 3}))


@pytest.mark.parametrize("text", ['r#"never closed // x', "'\\", 'let s = "open'])
def test_an_unclosed_rust_literal_runs_to_the_end(text: str) -> None:
    assert _texts(text, RUST) == []


def test_a_single_line_string_ends_at_the_line_break() -> None:
    assert _texts('x = \'open\n// real\ny = "a\\\nb" // after', TYPESCRIPT) == [
        (2, " real"),
        (4, " after"),
    ]


def test_a_string_ending_in_a_backslash_runs_to_the_end() -> None:
    assert _texts('x = "a\\', PROTO) == []


@pytest.mark.parametrize(
    "line",
    [
        "const u = `http://x`;",
        "const u = `a\\`// b`;",
        "const r = /[/]/g;",
        "const r = /a\\/\\/b/;",
        "if (/\\/\\//.test(s)) {}",
        "return /x\\/\\/y/.test(s);",
        "/a\\/\\/b/.test(s);",
    ],
)
def test_typescript_literals_hide_comment_markers(line: str) -> None:
    assert _texts(line, TYPESCRIPT) == []


def test_a_template_expression_is_code_that_may_hold_comments() -> None:
    text = "const s = `a${ {k: 1}.k /* c */ + `d${e}` }f//g`;\nh(); // real"
    assert _texts(text, TYPESCRIPT) == [(1, " c"), (2, " real")]


def test_a_template_may_span_lines() -> None:
    comments = slash_comments("const s = `one\n// two\n`;\n// three", TYPESCRIPT)
    assert (comments.lines, comments.code) == ([CommentLine(4, " three")], frozenset({1, 2, 3}))


def test_an_unclosed_template_runs_to_the_end() -> None:
    assert _texts("const s = `open // x", TYPESCRIPT) == []


@pytest.mark.parametrize(
    "line",
    [
        "const d = a / b; // real",
        "const d = (a) / 2 / 3; // real",
        "<br/> // real",
        "x = </p> // real",
    ],
)
def test_a_slash_after_a_value_is_division(line: str) -> None:
    assert _texts(line, TYPESCRIPT) == [(1, " real")]


def test_a_regex_ends_at_the_line_break() -> None:
    assert _texts("x = /abc\n// real\ny = /a\\", TYPESCRIPT) == [(2, " real")]


def test_css_has_no_line_comments() -> None:
    text = 'a { b: url(//x); content: "/* no */"; } /* yes */'
    assert _texts(text, CSS) == [(1, " yes")]


def test_proto_strings_take_either_quote() -> None:
    assert _texts("option x = '//'; // real\nstring s = 1;", PROTO) == [(1, " real")]


def test_rust_strings_are_returned_with_the_line_they_start_on() -> None:
    text = 'let a = "one two";\nlet b = r#"three "four""#;\nlet c = b"five";\nlet d = "six\nseven";'
    assert slash_strings(text, RUST) == [
        (1, "one two"),
        (2, 'three "four"'),
        (3, "five"),
        (4, "six\nseven"),
    ]


def test_char_literals_lifetimes_comments_and_regexes_are_not_strings() -> None:
    assert slash_strings("fn f<'a>(c: &'a str) { let q = '\"'; } // \"no\"", RUST) == []
    assert slash_strings('const r = /a "b"/; /* "no" */', TYPESCRIPT) == []


def test_a_string_keeps_its_escapes() -> None:
    assert slash_strings('x = "a \\" b";', TYPESCRIPT) == [(1, 'a \\" b')]


def test_a_template_holds_a_placeholder_for_each_expression() -> None:
    text = "const s = `a ${b} c ${`d ${e}`} \\`f`;\nconst t = `g\nh`;"
    assert slash_strings(text, TYPESCRIPT) == [(1, "a {} c {} \\`f"), (1, "d {}"), (2, "g\nh")]


@pytest.mark.parametrize(
    ("text", "syntax", "found"),
    [
        ('r#"never closed', RUST, "never closed"),
        ('let s = "open', RUST, "open"),
        ("x = 'open\ny", TYPESCRIPT, "open"),
        ("const s = `open", TYPESCRIPT, "open"),
    ],
)
def test_an_unclosed_string_holds_the_text_up_to_where_it_stops(
    text: str, syntax: Syntax, found: str
) -> None:
    assert slash_strings(text, syntax) == [(1, found)]
