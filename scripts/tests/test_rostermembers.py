"""Tests for the readers that say what the tree holds under each roster.

The fixtures are miniatures of the real things: one Rust suite with stacked attributes, one
`scripts/` directory with a vocabulary file beside its parts. Each test asks whether the answer
comes from the thing itself, because a roster compared against a second description of the tree
would compare two documents rather than the tree.
"""

from pathlib import Path

import pytest

import rostermembers
import scanrecipes
from rostermembers import (
    MemberError,
    cli_gate_modules,
    cross_tree_scans,
    gate_modules,
    ignored_tests,
    library_gate_modules,
    live_seam_checks,
    registry_tuples,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

SUITE = """\
//! Live seam checks, `#[ignore]`d so they never run in CI.

use std::time::Duration;

#[tokio::test]
#[ignore = "live seam check: needs a real brain at CORTEX_BRAIN_ADDR"]
async fn the_brain_answers() {
    assert!(true);
}

/// A helper the suite shares. Not ignored, so not a check.
fn patient_reads() -> Duration {
    Duration::from_millis(400)
}

#[tokio::test]
#[ignore = "live seam check: needs no brain"]
async fn the_probe_gives_up() {
    assert!(true);
}
"""


def suite(root: Path, text: str = SUITE) -> Path:
    """Write a miniature live suite where the real one lives, and return the root it is under."""
    path = root / rostermembers.LIVE_SEAM
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return root


def gates(root: Path, *names: str) -> Path:
    """Write a miniature `scripts/` holding exactly ``names``, and return the root over it."""
    tree = root / rostermembers.GATES
    tree.mkdir(parents=True, exist_ok=True)
    for name in names:
        (tree / name).write_text('"""A miniature."""\n', encoding="utf-8")
    return root


# ── the ignored checks in one Rust suite ───────────────────────────────────────


def test_every_ignored_check_is_read_and_nothing_else_is(tmp_path: Path) -> None:
    assert live_seam_checks(suite(tmp_path)) == frozenset(
        {"the_brain_answers", "the_probe_gives_up"}
    )


def test_a_helper_beside_the_checks_is_not_one() -> None:
    """The reader keys on the `#[ignore]` attribute, so an ordinary function in the file is not
    read as a check."""
    assert "patient_reads" not in ignored_tests(SUITE)


def test_the_name_is_taken_from_below_the_whole_attribute_stack() -> None:
    """`#[ignore]` is written above or below `#[tokio::test]`, so the first fn below wins."""
    swapped = SUITE.replace(
        '#[tokio::test]\n#[ignore = "live seam check: needs no brain"]',
        '#[ignore = "live seam check: needs no brain"]\n#[tokio::test]',
    )
    assert ignored_tests(swapped) == ["the_brain_answers", "the_probe_gives_up"]


def test_an_ignore_quoted_in_a_doc_comment_is_not_a_check() -> None:
    """The module comment of the real suite quotes the attribute, which is prose about it."""
    assert ignored_tests("//! `#[ignore]`d so they never run in CI.\n") == []


def test_a_check_nested_in_a_module_is_still_a_check() -> None:
    """Indentation is allowed deliberately, and nothing in the tree uses the allowance yet.

    A Rust suite that groups its checks in a `mod` block indents every attribute inside it, so a
    reader that required column zero would report a whole group as no checks at all. The tree
    carries no such block today, which is why the shape is pinned here: nothing else in the suite
    would fail if the allowance were dropped.
    """
    nested = "mod live {\n" + "\n".join(f"    {line}" for line in SUITE.splitlines()) + "\n}\n"
    assert ignored_tests(nested) == ["the_brain_answers", "the_probe_gives_up"]


def test_an_ignore_above_no_function_refuses_to_name_a_check(tmp_path: Path) -> None:
    """An `#[ignore]` above no function raises, since reporting the file's next name would invent
    a check.

    The line number is in the message because a suite where this happens is mid-edit, so the
    message says where to look rather than what the answer would have been.
    """
    dangling = SUITE + '\n#[ignore = "live seam check: needs nothing"]\n'
    with pytest.raises(MemberError, match="the ignore on line 22 sits above no function"):
        live_seam_checks(suite(tmp_path, dangling))


def test_a_suite_with_no_ignored_check_left_is_a_failure(tmp_path: Path) -> None:
    """An empty answer raises, since a comparison over nothing would report success every time it
    ran."""
    with pytest.raises(MemberError, match="came back empty"):
        live_seam_checks(suite(tmp_path, "//! Nothing ignored here.\n"))


def test_a_suite_that_is_not_there_is_named(tmp_path: Path) -> None:
    with pytest.raises(MemberError, match="cannot read body/crates/rpc/tests/live"):
        live_seam_checks(tmp_path)


# ── the modules this tree is a contract for ────────────────────────────────────


def test_every_module_in_the_gate_tree_is_a_member(tmp_path: Path) -> None:
    assert gate_modules(gates(tmp_path, "linecap.py", "dashcheck.py")) == frozenset(
        {"linecap.py", "dashcheck.py"}
    )


def test_a_gate_tree_that_is_not_there_is_named(tmp_path: Path) -> None:
    with pytest.raises(MemberError, match="scripts is not a directory"):
        gate_modules(tmp_path)


def test_a_gate_tree_holding_no_module_is_a_failure(tmp_path: Path) -> None:
    with pytest.raises(MemberError, match="came back empty"):
        gate_modules(gates(tmp_path))


# ── the two halves that same tree sorts into ───────────────────────────────────

GUARD = '"""A miniature with a command line."""\n\n\nif __name__ == "__main__":\n    main()\n'


def split(root: Path, *, runs: tuple[str, ...], read: tuple[str, ...]) -> Path:
    """Write a miniature `scripts/` where ``runs`` carry a main guard and ``read`` do not."""
    gates(root, *read)
    tree = root / rostermembers.GATES
    for name in runs:
        (tree / name).write_text(GUARD, encoding="utf-8")
    return root


def test_a_module_has_a_cli_exactly_when_it_carries_a_main_guard(tmp_path: Path) -> None:
    root = split(tmp_path, runs=("linecap.py",), read=("skippeddirs.py", "values.py"))
    assert cli_gate_modules(root) == frozenset({"linecap.py"})
    assert library_gate_modules(root) == frozenset({"skippeddirs.py", "values.py"})


def test_the_two_halves_are_the_whole_tree_and_share_nothing(tmp_path: Path) -> None:
    """The two halves are a partition of the directory, which is what lets each be held to a roster
    of its own."""
    root = split(tmp_path, runs=("linecap.py",), read=("values.py",))
    assert cli_gate_modules(root) | library_gate_modules(root) == gate_modules(root)
    assert not cli_gate_modules(root) & library_gate_modules(root)


def test_a_guard_that_is_not_at_the_top_level_is_not_a_cli(tmp_path: Path) -> None:
    """An indented guard sits inside a function and a quoted one is prose about a guard, so neither
    makes the module a CLI."""
    root = gates(tmp_path, "values.py")
    (tmp_path / rostermembers.GATES / "values.py").write_text(
        '"""Prose quoting `if __name__ == "__main__":` as the thing a CLI carries."""\n'
        "\n\ndef nested() -> None:\n"
        '    if __name__ == "__main__":\n        pass\n',
        encoding="utf-8",
    )
    assert library_gate_modules(root) == frozenset({"values.py"})
    with pytest.raises(MemberError, match="came back empty"):
        cli_gate_modules(root)


def test_a_tree_whose_every_module_is_a_cli_leaves_the_other_half_empty(tmp_path: Path) -> None:
    """Either half coming back empty raises, since an empty set matches any roster compared against
    it."""
    root = split(tmp_path, runs=("linecap.py",), read=())
    with pytest.raises(MemberError, match="came back empty"):
        library_gate_modules(root)


def test_a_module_that_cannot_be_read_is_named_rather_than_sorted(tmp_path: Path) -> None:
    """A file the reader cannot open raises, since sorting it into a half would report a claim
    about a module nothing read."""
    root = split(tmp_path, runs=("linecap.py",), read=("values.py",))
    (root / rostermembers.GATES / "values.py").write_bytes(b"\xff\xfe not text at all")
    with pytest.raises(MemberError, match=r"cannot read scripts/values\.py"):
        library_gate_modules(root)


# ── the scans the single gate runs, which are no directory's listing ───────────


def test_a_disagreement_between_the_two_files_arrives_as_a_member_failure(tmp_path: Path) -> None:
    """`rosternames.py` raises on the disagreement, and this is how that reaches a roster's far
    side."""
    (tmp_path / scanrecipes.JUSTFILE).write_text(
        "check:\n    just check-linecap\n", encoding="utf-8"
    )
    workflow = tmp_path / scanrecipes.WORKFLOW
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "jobs:\n  cross-tree:\n    steps:\n      - run: just check-backlog\n", encoding="utf-8"
    )
    with pytest.raises(MemberError, match="neither list is the answer while they disagree"):
        cross_tree_scans(tmp_path)


def test_a_gate_that_runs_no_scan_at_all_is_a_failure(tmp_path: Path) -> None:
    """Two files agreeing that there are no scans raises, which is the empty answer every floor
    here rejects."""
    (tmp_path / scanrecipes.JUSTFILE).write_text("check:\n    echo nothing\n", encoding="utf-8")
    workflow = tmp_path / scanrecipes.WORKFLOW
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text("jobs:\n  cross-tree:\n    steps:\n      - uses: a@b\n", encoding="utf-8")
    with pytest.raises(MemberError, match="came back empty"):
        cross_tree_scans(tmp_path)


def test_the_real_gate_runs_the_scans_this_repo_documents() -> None:
    assert "rostercheck.py" in cross_tree_scans(REPO_ROOT)


# ── the tuples the constant registry is joined from ────────────────────────────


def test_a_part_is_read_as_the_tuple_name_its_file_name_gives_it(tmp_path: Path) -> None:
    root = gates(tmp_path, "seamcouplings.py", "logcouplings.py", "couplings.py", "registry.py")
    assert registry_tuples(root) == frozenset({"SEAM_COUPLINGS", "LOG_COUPLINGS"})


def test_the_vocabulary_file_is_not_a_part(tmp_path: Path) -> None:
    """`couplings.py` is what every part is written in, so a roster naming it would be wrong."""
    root = gates(tmp_path, "seamcouplings.py", "couplings.py")
    assert registry_tuples(root) == frozenset({"SEAM_COUPLINGS"})


def test_a_registry_with_no_part_but_its_vocabulary_is_a_failure(tmp_path: Path) -> None:
    with pytest.raises(MemberError, match="came back empty"):
        registry_tuples(gates(tmp_path, "couplings.py"))


# ── against the tree these readers are written for ─────────────────────────────


def test_the_real_suite_and_the_real_registry_are_both_read() -> None:
    """The fixtures above are miniatures, so the real files are read here too.

    Floors are asserted rather than the exact sets, since the counts are what this repo holds
    today and a check or a part landing tomorrow should not fail here.
    """
    assert len(live_seam_checks(REPO_ROOT)) > 1
    assert len(registry_tuples(REPO_ROOT)) > 1
    assert "rostermembers.py" in gate_modules(REPO_ROOT)


def test_the_real_tree_really_holds_both_halves() -> None:
    """Both halves are filled by the committed tree, so neither roster is held to an empty set."""
    assert "rostercheck.py" in cli_gate_modules(REPO_ROOT)
    assert "rostermembers.py" in library_gate_modules(REPO_ROOT)
    assert cli_gate_modules(REPO_ROOT) | library_gate_modules(REPO_ROOT) == gate_modules(REPO_ROOT)
