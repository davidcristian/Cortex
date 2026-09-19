"""Find the comments in Rust, TypeScript, CSS and protobuf source, skipping string literals."""

import re
from typing import NamedTuple

from commentblocks import CommentLine, Comments


class Syntax(NamedTuple):
    """Which comment and literal forms a language has."""

    line_comments: bool
    nested_blocks: bool
    quotes: str
    multiline_strings: bool
    rust_literals: bool
    templates_and_regexes: bool


_PLAIN = Syntax(
    line_comments=True,
    nested_blocks=False,
    quotes="\"'",
    multiline_strings=False,
    rust_literals=False,
    templates_and_regexes=False,
)
RUST = _PLAIN._replace(nested_blocks=True, quotes='"', multiline_strings=True, rust_literals=True)
TYPESCRIPT = _PLAIN._replace(templates_and_regexes=True)
CSS = _PLAIN._replace(line_comments=False)
PROTO = _PLAIN
SYNTAXES = {".rs": RUST, ".ts": TYPESCRIPT, ".tsx": TYPESCRIPT, ".css": CSS, ".proto": PROTO}

_RAW_STRING = re.compile(r'[bc]?r(#*)"')
_WORD = re.compile(r"[\w$]+")
_REGEX_AFTER = frozenset("(,=:[!&|?{;+-*%~^")
_REGEX_KEYWORDS = frozenset(
    {"return", "typeof", "case", "do", "else", "in", "of", "new", "delete", "void", "throw"}
    | {"instanceof", "yield", "await"}
)


class _Lexer:
    def __init__(self, text: str, syntax: Syntax) -> None:
        self.text = text
        self.syntax = syntax
        self.pos = 0
        self.line = 1
        self.code: set[int] = set()
        self.spanned: set[int] = set()
        self.found: dict[int, list[str]] = {}
        self.previous = ""
        self.word = ""

    def comments(self) -> Comments:
        self.code_until_brace(closing=False)
        lines = [
            CommentLine(line=number, text=" ".join(texts))
            for number, texts in sorted(self.found.items())
        ]
        return Comments(lines=lines, code=frozenset(self.code - self.spanned))

    def at(self, marker: str) -> bool:
        return self.text.startswith(marker, self.pos)

    def newline(self) -> None:
        self.line += 1
        self.pos += 1

    def code_until_brace(self, *, closing: bool) -> None:
        depth = 0
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == "\n":
                self.newline()
            elif char.isspace():
                self.pos += 1
            elif self.syntax.line_comments and self.at("//"):
                self.line_comment()
            elif self.at("/*"):
                self.block_comment()
            elif closing and char == "}" and depth == 0:
                self.code.add(self.line)
                self.pos += 1
                return
            else:
                self.code.add(self.line)
                depth += {"{": 1, "}": -1}.get(char, 0)
                self.token(char)

    def token(self, char: str) -> None:
        syntax = self.syntax
        after = self.word
        self.word = ""
        if syntax.rust_literals and self.raw_string():
            return
        if syntax.rust_literals and char == "'":
            self.char_or_lifetime()
        elif char in syntax.quotes:
            self.string(char)
        elif syntax.templates_and_regexes and char == "`":
            self.template()
        elif syntax.templates_and_regexes and char == "/" and self.regex_allowed(after):
            self.regex()
        elif found := _WORD.match(self.text, self.pos):
            self.word = found.group()
            self.previous = self.word[-1]
            self.pos = found.end()
        else:
            self.previous = char
            self.pos += 1

    def skip_to(self, end: int) -> None:
        for _ in range(self.text.count("\n", self.pos, end)):
            self.line += 1
            self.code.add(self.line)
        self.pos = end

    def line_comment(self) -> None:
        end = self.text.find("\n", self.pos)
        end = len(self.text) if end < 0 else end
        text = self.text[self.pos + 2 : end]
        self.record(self.line, text[1:] if text[:1] in ("/", "!") else text)
        self.pos = end

    def block_comment(self) -> None:
        depth, index = 0, self.pos
        while index < len(self.text):
            if self.text.startswith("/*", index):
                depth += 1 if self.syntax.nested_blocks or depth == 0 else 0
                index += 2
            elif self.text.startswith("*/", index):
                depth -= 1
                index += 2
                if depth == 0:
                    break
            else:
                index += 1
        pieces = self.text[self.pos : index].split("\n")
        for offset, piece in enumerate(pieces):
            self.record(self.line + offset, _clean(piece, first=offset == 0))
        if len(pieces) > 1:
            self.spanned.update(range(self.line, self.line + len(pieces)))
        self.line += len(pieces) - 1
        self.pos = index

    def record(self, line: int, text: str) -> None:
        self.found.setdefault(line, []).append(text.rstrip())

    def string(self, quote: str) -> None:
        index = self.pos + 1
        while index < len(self.text) and self.text[index] != quote:
            if self.text[index] == "\n" and not self.syntax.multiline_strings:
                break
            index += 2 if self.text[index] == "\\" else 1
        closed = self.text[index : index + 1] == quote
        self.skip_to(index + 1 if closed else min(index, len(self.text)))
        self.previous = quote

    def raw_string(self) -> bool:
        found = _RAW_STRING.match(self.text, self.pos)
        if found is None:
            return False
        end = self.text.find('"' + found.group(1), found.end())
        self.skip_to(len(self.text) if end < 0 else end + 1 + len(found.group(1)))
        self.previous = '"'
        return True

    def char_or_lifetime(self) -> None:
        text, pos = self.text, self.pos
        if text[pos + 1 : pos + 2] == "\\":
            end = text.find("'", pos + 3)
            self.skip_to(len(text) if end < 0 else end + 1)
        elif text[pos + 2 : pos + 3] == "'":
            self.pos += 3
        else:
            self.pos += 1
        self.previous = "'"

    def template(self) -> None:
        self.pos += 1
        while self.pos < len(self.text) and not self.at("`"):
            if self.at("${"):
                self.pos += 2
                self.code_until_brace(closing=True)
            else:
                self.skip_to(self.pos + (2 if self.at("\\") else 1))
        self.pos += 1
        self.previous = "`"

    def regex_allowed(self, word: str) -> bool:
        return not self.previous or self.previous in _REGEX_AFTER or word in _REGEX_KEYWORDS

    def regex(self) -> None:
        index, in_class = self.pos + 1, False
        while index < len(self.text) and self.text[index] != "\n":
            char = self.text[index]
            if char == "/" and not in_class:
                index += 1
                break
            in_class = (in_class or char == "[") and char != "]"
            index += 2 if char == "\\" else 1
        self.skip_to(index)
        self.previous = "/"


def _clean(piece: str, *, first: bool) -> str:
    text = piece.removesuffix("*/")
    if first:
        text = text[2:]
        return text[1:] if text[:1] in ("*", "!") else text
    return text.lstrip().removeprefix("*")


def slash_comments(text: str, syntax: Syntax) -> Comments:
    return _Lexer(text, syntax).comments()
