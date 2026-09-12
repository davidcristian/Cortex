"""Tests for what a markdown fence is to every reader in this tree.

Two kinds of claim are here. The first is what a fence is: which lines are one, which lines carrying
the same characters are not, and how much of the spec that reading covers. The second is the
obligation the shared answer exists to make unnecessary, and it is the one that matters: a module
under `scripts/` that spells a fence marker of its own is reported by name.

That obligation runs over the modules and not over the suites beside them. A test writes the
markdown its reader is asked about, so a marker in a test is the document under test rather than a
second answer to the question this module answers.
"""

import ast
from pathlib import Path

import pytest

import moduleconstants
from markdownfences import MARKERS, is_fence, spelled

GATES = Path(__file__).resolve().parents[1]
# The one module allowed to spell a fence marker, which is the whole rule the last test holds.
SPELLING = "markdownfences.py"


@pytest.mark.parametrize("marker", MARKERS)
def test_either_marker_opens_a_block(marker: str) -> None:
    """Backticks and tildes are both markdown's, and a reader here has to take either."""
    assert is_fence(marker)


@pytest.mark.parametrize("line", ["```text", "~~~bash", "   ```", "\t~~~", "  ```json lines"])
def test_an_indent_and_an_info_string_are_part_of_the_opening_line(line: str) -> None:
    """A fence written inside a list item is still a fence, and so is one naming its language."""
    assert is_fence(line)


@pytest.mark.parametrize("line", ["", "prose", "`` not three", "run `x` now", "text ```", " ~~ "])
def test_what_carries_no_marker_at_the_start_of_the_line_is_not_a_fence(line: str) -> None:
    """Two characters are a code span's, and a marker mid-line is text inside a sentence."""
    assert not is_fence(line)


def test_a_longer_run_of_the_marker_is_read_as_a_fence() -> None:
    """Markdown allows more than three, and the reading here stops at the first three."""
    assert is_fence("`````")
    assert is_fence("~~~~")


def _spelled(source: str) -> list[int]:
    """Every line of one source fragment where a fence marker is written into code."""
    return spelled(ast.parse(source))


def test_a_marker_written_into_code_is_reported_by_its_line() -> None:
    """Any literal carrying a marker is a reader answering the question a second time."""
    source = (
        'x = 1\nFENCE = re.compile(r"^\\s*(?:```|~~~)")\nif line.startswith("~~~"):\n    pass\n'
    )
    assert _spelled(source) == [2, 3]


def test_a_marker_inside_a_docstring_is_prose_and_not_a_spelling() -> None:
    """A module, a class and a function may all say what a fence is without answering for one."""
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
    assert _spelled(source) == []


def test_a_literal_carrying_no_marker_is_not_reported() -> None:
    """The report is about the marker and not about strings, of which every module is full."""
    assert _spelled('name = "backtick"\ncount = 3\nempty = ""\n') == []


def test_a_bare_expression_that_is_not_a_string_leaves_the_literals_beside_it_held() -> None:
    """A statement that is a call is not a docstring, and the marker below it is still code."""
    assert _spelled('do_something()\nopener = "```"\n') == [2]


def test_two_docstrings_with_the_same_text_are_both_passed_over() -> None:
    """Compared by identity, so one docstring does not exempt another that reads the same."""
    source = '"""Says ```."""\n\n\ndef f():\n    """Says ```."""\n'
    assert _spelled(source) == []


def test_no_module_here_spells_a_fence_of_its_own() -> None:
    """Every fence marker under `scripts/` is written in the one module that answers for it.

    This is the obligation the three copies made necessary: `headingshapes.py`, `logsamples.py`
    and `commitlint.py` each held the same pattern, they agreed by inspection, and nothing would
    have reported a fourth reader arriving with a pattern that differed. The set is compared whole
    rather than as a floor plus an empty offender list, so a reading that finds nothing at all
    fails too, and the shared module's own spellings are held to one line, the tuple naming the
    markers.
    """
    spellings = {
        path.name: spelled(moduleconstants.parse(path, path.name)) for path in GATES.glob("*.py")
    }
    assert {name for name, lines in spellings.items() if lines} == {SPELLING}
    assert len(set(spellings[SPELLING])) == 1
