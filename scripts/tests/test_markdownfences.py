import ast
from pathlib import Path

import pytest

import moduleconstants
from markdownfences import MARKERS, Fences, marker_lines

SCRIPTS = Path(__file__).resolve().parents[1]
MARKER_MODULE = "markdownfences.py"


def _opens(line: str) -> bool:
    """Whether ``line`` opens a block when nothing is open yet."""
    return Fences().bounds(line)


@pytest.mark.parametrize("marker", MARKERS)
def test_either_marker_opens_a_block(marker: str) -> None:
    assert _opens(marker)


@pytest.mark.parametrize("line", ["```text", "~~~bash", "   ```", "\t~~~", "  ```json lines"])
def test_an_indent_and_an_info_string_are_part_of_the_opening_line(line: str) -> None:
    assert _opens(line)


@pytest.mark.parametrize("line", ["", "prose", "`` not three", "run `x` now", "text ```", " ~~ "])
def test_what_has_no_marker_at_the_start_of_the_line_is_not_a_fence(line: str) -> None:
    assert not _opens(line)


def test_a_longer_run_of_the_marker_opens_a_block_of_its_own_length() -> None:
    long_run = Fences()
    assert long_run.bounds("`````")
    assert not long_run.bounds("```")
    assert long_run.inside


def test_nothing_is_open_before_a_line_is_read() -> None:
    assert not Fences().inside


def test_a_marker_of_the_opening_length_closes_the_block() -> None:
    fences = Fences()
    assert fences.bounds("```text")
    assert fences.inside
    assert fences.bounds("```")
    assert not fences.inside


def test_a_shorter_marker_inside_a_longer_block_is_text() -> None:
    fences = Fences()
    assert fences.bounds("````")
    assert not fences.bounds("```json")
    assert fences.inside
    assert fences.bounds("````")
    assert not fences.inside


def test_the_other_character_inside_a_block_is_text() -> None:
    fences = Fences()
    assert fences.bounds("```")
    assert not fences.bounds("~~~~~")
    assert fences.inside


def test_a_line_with_no_marker_bounds_nothing_inside_a_block_or_outside_one() -> None:
    fences = Fences()
    assert not fences.bounds("prose")
    assert not fences.inside
    assert fences.bounds("```")
    assert not fences.bounds("prose")
    assert fences.inside


def test_what_would_close_the_block_is_answered_without_reading_it() -> None:
    fences = Fences()
    fences.bounds("````")
    assert not fences.closes("```")
    assert not fences.closes("prose")
    assert fences.closes("````")
    assert fences.inside


def test_outside_a_block_nothing_closes_one() -> None:
    assert not Fences().closes("```")


def _marker_lines(source: str) -> list[int]:
    """Return every line of ``source`` where a fence marker is written into the code."""
    return marker_lines(ast.parse(source))


def test_a_marker_written_into_code_is_reported_by_its_line() -> None:
    source = (
        'x = 1\nFENCE = re.compile(r"^\\s*(?:```|~~~)")\nif line.startswith("~~~"):\n    pass\n'
    )
    assert _marker_lines(source) == [2, 3]


def test_a_marker_inside_a_docstring_is_prose_and_not_a_form() -> None:
    source = (
        '"""A module saying ``` out loud."""\n'
        "\n"
        "\n"
        "class Thing:\n"
        '    """A class saying ~~~ out loud."""\n'
        "\n"
        "    def method(self):\n"
        '        """A method saying ``` out loud."""\n'
        "\n"
        "\n"
        "def other():\n"
        '    """Another docstring saying the same ```."""\n'
    )
    assert _marker_lines(source) == []


def test_a_literal_with_no_marker_is_not_reported() -> None:
    assert _marker_lines('name = "backtick"\ncount = 3\nempty = ""\n') == []


def test_a_bare_expression_that_is_not_a_string_leaves_the_literals_beside_it_held() -> None:
    assert _marker_lines('do_something()\nopener = "```"\n') == [2]


def test_two_docstrings_with_the_same_text_are_both_passed_over() -> None:
    source = '"""Says ```."""\n\n\ndef f():\n    """Says ```."""\n'
    assert _marker_lines(source) == []


def test_no_module_here_writes_a_fence_of_its_own() -> None:
    marker_modules = {
        path.name: marker_lines(moduleconstants.parse(path, path.name))
        for path in SCRIPTS.glob("*.py")
    }
    assert {name for name, lines in marker_modules.items() if lines} == {MARKER_MODULE}
    assert len(set(marker_modules[MARKER_MODULE])) == 1
