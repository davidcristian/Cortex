from pathlib import Path

import pytest

import bannedwords
from bannedwords import Hit, Table

TABLE = """# Rules

| Do not write | Write instead |
| --- | --- |
| gate, gates | check |
| in force, Under The Hood | current |
| re-derive | recompute |

After the table.
"""
WORDS = ("gate", "gates", "in force", "under the hood", "re-derive")
PATTERN = bannedwords.compile_words(WORDS)


def _hits(*lines: str) -> list[Hit]:
    return bannedwords.find_words(list(enumerate(lines, start=1)), PATTERN)


def test_the_first_column_is_read_in_lower_case_with_the_table_lines() -> None:
    assert bannedwords.parse_table(TABLE, "AGENTS.md") == Table(words=WORDS, first=3, last=7)


def test_a_table_at_the_end_of_the_file_is_read_whole() -> None:
    text = "| Do not write | Write instead |\n|:---|---:|\n| Knob | setting |"
    assert bannedwords.parse_table(text, "x") == Table(words=("knob",), first=1, last=3)


def test_the_first_table_with_the_header_is_the_one_read() -> None:
    text = "| a | b |\n\n| Do not write | x |\n| --- | --- |\n| knob | y |\n\n"
    text += "| Do not write |\n| z |\n"
    assert bannedwords.parse_table(text, "x").words == ("knob",)


def test_a_file_without_the_table_is_an_error() -> None:
    with pytest.raises(bannedwords.TableError) as caught:
        bannedwords.parse_table("| a | b |\n| --- | --- |\n", "AGENTS.md")
    assert str(caught.value) == "AGENTS.md has no table whose first column is headed 'Do not write'"


def test_a_table_that_lists_no_word_is_an_error() -> None:
    text = "| Do not write | Write instead |\n| --- | --- |\n| , | x |\n"
    with pytest.raises(bannedwords.TableError) as caught:
        bannedwords.parse_table(text, "AGENTS.md")
    assert str(caught.value) == "the banned-word table in AGENTS.md lists no word"


def test_read_table_reads_the_file(tmp_path: Path) -> None:
    path = tmp_path / "AGENTS.md"
    path.write_text(TABLE, encoding="utf-8")
    assert bannedwords.read_table(path).words == WORDS


def test_read_table_reports_a_file_it_cannot_read(tmp_path: Path) -> None:
    with pytest.raises(bannedwords.TableError, match="cannot read"):
        bannedwords.read_table(tmp_path / "missing.md")


def test_the_table_in_agents_md_is_readable() -> None:
    assert "load-bearing" in bannedwords.read_table(bannedwords.RULES).words


def test_words_match_whole_words_in_any_case() -> None:
    assert _hits("The Gate and the GATES", "a gateway, an aggregate, gate_name, gate2") == [
        Hit(1, "gate"),
        Hit(1, "gates"),
    ]


def test_punctuation_and_hyphens_end_a_word() -> None:
    assert _hits("self-gate, (gate) gate's") == [Hit(1, "gate")] * 3


def test_a_hyphenated_entry_matches_as_written() -> None:
    assert _hits("re-derive it, but not derive or rederive") == [Hit(1, "re-derive")]


def test_a_phrase_split_across_a_line_break_is_reported_on_its_first_line() -> None:
    assert _hits("the rule in", "  force today") == [Hit(1, "in force")]


def test_a_phrase_that_starts_on_the_next_line_is_reported_there() -> None:
    assert _hits("nothing here", "what is under the  hood") == [Hit(2, "under the hood")]


def test_a_word_at_the_start_of_the_next_line_is_reported_once() -> None:
    assert _hits("gate", "gate") == [Hit(1, "gate"), Hit(2, "gate")]


def test_code_spans_link_targets_and_urls_are_not_searched() -> None:
    lines = (
        "`gate` and ``a `gate` here`` and [a gate](docs/gate.md) and https://x.org/gate",
        "[ref]: https://example.com/gate",
    )
    assert _hits(*lines) == [Hit(1, "gate")]


def test_a_code_span_may_cross_a_line_break() -> None:
    assert _hits("the `just", "gate` recipe") == []


def test_an_unclosed_backtick_is_text() -> None:
    assert _hits("a ` gate") == [Hit(1, "gate")]


def test_mask_keeps_line_breaks() -> None:
    assert bannedwords.mask("`a\nb` c") == "\0\0\n\0\0 c"


def test_runs_split_at_gaps_and_blank_lines() -> None:
    lines = [(1, "a"), (2, "b"), (3, " "), (4, "c"), (6, "d")]
    assert bannedwords.runs(lines) == [[(1, "a"), (2, "b")], [(4, "c")], [(6, "d")]]


def test_a_phrase_is_not_found_across_a_blank_line() -> None:
    runs = bannedwords.runs([(1, "rule in"), (2, ""), (3, "force")])
    assert [bannedwords.find_words(run, PATTERN) for run in runs] == [[], []]
