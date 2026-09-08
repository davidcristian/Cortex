import ast
from pathlib import Path

import gatecalls
import moduleconstants
from treewalk import walk_files

GATES = Path(__file__).resolve().parents[1]
DESCENT = "treewalk.py"


def _tree(root: Path) -> None:
    """Write a small tree with one of everything the walk is asked about."""
    (root / "top.md").write_text("top", encoding="utf-8")
    (root / "inside").mkdir()
    (root / "inside" / "deep.md").write_text("deep", encoding="utf-8")
    (root / "inside" / "nested").mkdir()
    (root / "inside" / "nested" / "deeper.md").write_text("deeper", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("[core]", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_thing.md").write_text("test", encoding="utf-8")


def test_the_skipped_trees_are_never_entered(tmp_path: Path) -> None:
    _tree(tmp_path)
    found = [path.relative_to(tmp_path).as_posix() for path in walk_files(tmp_path)]
    assert found == [
        "top.md",
        "inside/deep.md",
        "inside/nested/deeper.md",
        "tests/test_thing.md",
    ]


def test_a_caller_may_skip_more_than_the_shared_list(tmp_path: Path) -> None:
    _tree(tmp_path)
    found = [
        path.relative_to(tmp_path).as_posix()
        for path in walk_files(tmp_path, also_skip=frozenset({"tests", "nested"}))
    ]
    assert found == ["top.md", "inside/deep.md"]


def test_a_caller_may_refuse_a_directory_by_where_it_is(tmp_path: Path) -> None:
    _tree(tmp_path)
    refused = {"inside/nested"}
    found = [
        path.relative_to(tmp_path).as_posix()
        for path in walk_files(tmp_path, enter=lambda inside: inside.as_posix() not in refused)
    ]
    assert found == ["top.md", "inside/deep.md", "tests/test_thing.md"]


def test_what_is_not_a_regular_file_is_not_handed_on(tmp_path: Path) -> None:
    (tmp_path / "real.md").write_text("real", encoding="utf-8")
    (tmp_path / "gone.md").symlink_to(tmp_path / "absent.md")
    assert [path.name for path in walk_files(tmp_path)] == ["real.md"]


def test_every_tree_read_here_is_the_shared_one() -> None:
    readers = {
        path.name: gatecalls.tree_reads(moduleconstants.parse(path, path.name))
        for path in GATES.glob("*.py")
    }
    assert {name for name, reads in readers.items() if reads} == {DESCENT}
    assert [read.called for read in readers[DESCENT]] == ["walk"]


def test_a_syntax_walk_is_not_a_tree_read() -> None:
    source = "import ast\nfor node in ast.walk(tree):\n    pass\n"
    assert gatecalls.tree_reads(ast.parse(source)) == []
