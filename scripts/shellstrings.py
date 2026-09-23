"""Find the double-quoted strings in shell source and a justfile, each expansion a placeholder."""

import re

from slashcomments import PLACEHOLDER

_PARAMETER = re.compile(r"\$(?:[A-Za-z_]\w*|[0-9@*#?$!-])")
_OPENERS = {")": "(", "}": "{"}


class _Lexer:
    def __init__(self, text: str, *, just: bool) -> None:
        self.text = text
        self.just = just
        self.pos = 0
        self.line = 1
        self.strings: list[tuple[int, str]] = []

    def at(self, marker: str) -> bool:
        return self.text.startswith(marker, self.pos)

    def skip_to(self, end: int) -> None:
        self.line += self.text.count("\n", self.pos, end)
        self.pos = end

    def code(self, closer: str) -> None:
        depth = 0
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == closer and depth == 0:
                self.pos += 1
                return
            if char == "#" and (self.pos == 0 or self.text[self.pos - 1].isspace()):
                end = self.text.find("\n", self.pos)
                self.pos = len(self.text) if end < 0 else end
            elif char == "\\":
                self.skip_to(min(self.pos + 2, len(self.text)))
            elif char == "'":
                end = self.text.find("'", self.pos + 1)
                self.skip_to(len(self.text) if end < 0 else end + 1)
            elif char == '"':
                self.double()
            elif not self.expansion():
                depth += (char == _OPENERS.get(closer)) - (char == closer)
                self.skip_to(self.pos + 1)

    def expansion(self) -> bool:
        if self.at("$(") or self.at("${"):
            closer = ")" if self.at("$(") else "}"
            self.pos += 2
            self.code(closer)
        elif self.at("`"):
            self.pos += 1
            self.code("`")
        else:
            return False
        return True

    def double(self) -> None:
        line, pieces = self.line, list[str]()
        self.pos += 1
        while self.pos < len(self.text) and not self.at('"'):
            parameter = _PARAMETER.match(self.text, self.pos)
            if self.just and self.at("{{{{"):
                pieces.append("{{")
                self.pos += 4
            elif self.just and self.at("{{"):
                end = self.text.find("}}", self.pos)
                pieces.append(PLACEHOLDER)
                self.skip_to(len(self.text) if end < 0 else end + 2)
            elif parameter is not None:
                pieces.append(PLACEHOLDER)
                self.pos = parameter.end()
            elif self.expansion():
                pieces.append(PLACEHOLDER)
            else:
                step = 2 if self.at("\\") else 1
                pieces.append(self.text[self.pos : self.pos + step])
                self.skip_to(self.pos + step)
        self.strings.append((line, "".join(pieces)))
        self.pos += 1


def shell_strings(text: str, *, just: bool) -> list[tuple[int, str]]:
    """Return each double-quoted string's first line and its text, in line order.

    Escapes stay as written; ``just`` reads ``{{...}}`` as a placeholder and ``{{{{`` as ``{{``.
    """
    lexer = _Lexer(text, just=just)
    lexer.code("")
    return sorted(lexer.strings)
