"""Readable text from an HTML email body (ADR-0009 refinements addendum)."""

import re
from html.parser import HTMLParser

# Containers whose text content is not prose; everything inside them is dropped.
_DROP = frozenset({"head", "script", "style", "template", "title"})
# Tags that bound a line of prose: opening or closing one breaks the line.
_BREAK = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "fieldset",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tr",
        "ul",
    }
)
# Cells on one table row stay on one line, separated by spaces; the row tag breaks it.
_CELL = frozenset({"td", "th"})
# Any whitespace run inside character data (including source newlines) is one space;
# only markup (the _BREAK tags) may produce a line break in the output.
_WS = re.compile(r"\s+")


class _TextExtractor(HTMLParser):
    """Collect prose chunks; ``convert_charrefs`` (the default) decodes entities for us."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._drop_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in _DROP:
            self._drop_depth += 1
        else:
            self._boundary(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in _DROP:
            # A stray closing tag must not unbalance the counter below zero.
            self._drop_depth = max(0, self._drop_depth - 1)
        else:
            self._boundary(tag)

    def handle_data(self, data: str) -> None:
        if not self._drop_depth:
            self._parts.append(_WS.sub(" ", data))

    def _boundary(self, tag: str) -> None:
        if tag in _BREAK:
            self._parts.append("\n")
        elif tag in _CELL:
            self._parts.append(" ")

    @property
    def text(self) -> str:
        """The collected prose: tight lines, no blank lines, no edge whitespace."""
        lines = "".join(self._parts).split("\n")
        tidy = (" ".join(line.split()) for line in lines)
        return "\n".join(line for line in tidy if line)


def html_to_text(html: str) -> str:
    """Extract readable text from ``html``; empty when there is no prose to extract."""
    extractor = _TextExtractor()
    extractor.feed(html)
    extractor.close()
    return extractor.text
