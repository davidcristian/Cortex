import pytest

from cortex_core import REPLY_CAPPED_NOTE, DecodeStop, StopLedger, StopReason, TextDelta
from cortex_core.turn_output import append_note, cap_note, place_note

_NOTE = "\n\n(a note)"


@pytest.mark.parametrize(
    ("parts", "placed"),
    [
        ([], "(a note)"),
        (["", "  \n "], "(a note)"),
        (["an answer"], "\n\n(a note)"),
        (["a line", "\n"], "\n(a note)"),
        (["a paragraph\n\n"], "(a note)"),
        (["a list\n\n\n"], "(a note)"),
    ],
)
def test_a_note_sits_one_blank_line_below_text_and_opens_a_reply_with_none(
    parts: list[str], placed: str
) -> None:
    assert place_note(parts, _NOTE) == placed


def test_appending_a_note_stores_what_it_shows() -> None:
    parts = ["Here"]
    events = list(append_note(parts, _NOTE))
    assert events == [TextDelta(text="\n\n(a note)")]
    assert parts == ["Here", "\n\n(a note)"]


def test_a_capped_reply_with_no_text_is_the_note_alone() -> None:
    stops = StopLedger()
    stops.observe(DecodeStop(StopReason.CAPPED))
    parts: list[str] = []
    events = list(cap_note(stops, parts))
    assert events == [TextDelta(text=REPLY_CAPPED_NOTE.lstrip("\n"))]
    assert "".join(parts) == REPLY_CAPPED_NOTE.lstrip("\n")
