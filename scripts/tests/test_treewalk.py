"""Tests for the one descent every reader in this tree is handed its files by.

Two kinds of claim are here. The first is what the walk does: which trees it never enters, what a
caller may add to that, and what it refuses to hand on. The second is the obligation the walk
exists to make unnecessary, and it is the one that matters: a module under `scripts/` that reads a
directory tree of its own is reported by name, whatever shape that read is written in.
"""

import ast
from pathlib import Path

import gatecalls
import moduleconstants
from treewalk import walk_files

GATES = Path(__file__).resolve().parents[1]
# The one module allowed to descend a tree, which is the whole rule the last test holds.
DESCENT = "treewalk.py"


def _tree(root: Path) -> None:
    """Write a small tree holding one of everything the walk is asked about."""
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
    """A directory the shared list names is not descended, and everything else is.

    The file inside `.git` is written to be found: a walk that pruned nothing would hand it on,
    and one that pruned by suffix rather than by directory would too.
    """
    _tree(tmp_path)
    found = [path.relative_to(tmp_path).as_posix() for path in walk_files(tmp_path)]
    assert found == [
        "top.md",
        "inside/deep.md",
        "inside/nested/deeper.md",
        "tests/test_thing.md",
    ]


def test_a_caller_may_skip_more_than_the_shared_list(tmp_path: Path) -> None:
    """`also_skip` is the line cap's two extra names, and it adds rather than replaces."""
    _tree(tmp_path)
    found = [
        path.relative_to(tmp_path).as_posix()
        for path in walk_files(tmp_path, also_skip=frozenset({"tests", "nested"}))
    ]
    assert found == ["top.md", "inside/deep.md"]


def test_a_caller_may_refuse_a_directory_by_where_it_is(tmp_path: Path) -> None:
    """`enter` is asked about each directory by its path relative to the root, as the dash ban's is.

    The refused directory is named by its path rather than its name, which is the difference
    between this and `also_skip`: git ignores `coverage` under `body/app/` and nowhere else.
    """
    _tree(tmp_path)
    refused = {"inside/nested"}
    found = [
        path.relative_to(tmp_path).as_posix()
        for path in walk_files(tmp_path, enter=lambda inside: inside.as_posix() not in refused)
    ]
    assert found == ["top.md", "inside/deep.md", "tests/test_thing.md"]


def test_what_is_not_a_regular_file_is_not_handed_on(tmp_path: Path) -> None:
    """A dangling symlink is skipped, every reader here going on to open what it is given."""
    (tmp_path / "real.md").write_text("real", encoding="utf-8")
    (tmp_path / "gone.md").symlink_to(tmp_path / "absent.md")
    assert [path.name for path in walk_files(tmp_path)] == ["real.md"]


def test_every_tree_read_here_is_the_shared_one() -> None:
    """No module under `scripts/` descends a directory tree except `treewalk.py`.

    This is the obligation the two searches before it could not keep. One looked for the pruning
    line `dirnames[:]` and so recognized four of the seven readers here; three arrived later
    written as a filtered `rglob` and were held to nothing. The set is compared whole rather than
    as a floor plus an empty offender list, so a reader that finds nothing at all fails too.
    """
    readers = {
        path.name: gatecalls.tree_reads(moduleconstants.parse(path, path.name))
        for path in GATES.glob("*.py")
    }
    assert {name for name, reads in readers.items() if reads} == {DESCENT}
    assert [read.called for read in readers[DESCENT]] == ["walk"]


def test_a_syntax_walk_is_not_a_tree_read() -> None:
    """`ast.walk` reads no directory, and the modules here that call it are not tree readers.

    Told apart by the module it is spelled on, which is why this is asserted over the real tree:
    six modules here walk a syntax tree, and a reader that counted them would report six faults
    nobody can fix.
    """
    source = "import ast\nfor node in ast.walk(tree):\n    pass\n"
    assert gatecalls.tree_reads(ast.parse(source)) == []
