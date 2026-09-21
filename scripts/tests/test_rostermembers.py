from pathlib import Path

import pytest

import rostermembers
import scanrecipes
from rostermembers import (
    MemberError,
    body_crates,
    brain_packages,
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
    """Write a small live suite where the real one lives, and return the root above it."""
    path = root / rostermembers.LIVE_SEAM
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return root


def gates(root: Path, *names: str) -> Path:
    """Write a small `scripts/` with exactly ``names`` in it, and return the root above it."""
    tree = root / rostermembers.GATES
    tree.mkdir(parents=True, exist_ok=True)
    for name in names:
        (tree / name).write_text('"""A miniature."""\n', encoding="utf-8")
    return root


def test_every_ignored_check_is_read_and_nothing_else_is(tmp_path: Path) -> None:
    assert live_seam_checks(suite(tmp_path)) == frozenset(
        {"the_brain_answers", "the_probe_gives_up"}
    )


def test_a_helper_beside_the_checks_is_not_one() -> None:
    assert "patient_reads" not in ignored_tests(SUITE)


def test_the_name_is_taken_from_below_the_whole_attribute_stack() -> None:
    swapped = SUITE.replace(
        '#[tokio::test]\n#[ignore = "live seam check: needs no brain"]',
        '#[ignore = "live seam check: needs no brain"]\n#[tokio::test]',
    )
    assert ignored_tests(swapped) == ["the_brain_answers", "the_probe_gives_up"]


def test_an_ignore_quoted_in_a_doc_comment_is_not_a_check() -> None:
    assert ignored_tests("//! `#[ignore]`d so they never run in CI.\n") == []


def test_a_check_nested_in_a_module_is_still_a_check() -> None:
    nested = "mod live {\n" + "\n".join(f"    {line}" for line in SUITE.splitlines()) + "\n}\n"
    assert ignored_tests(nested) == ["the_brain_answers", "the_probe_gives_up"]


def test_an_ignore_above_no_function_refuses_to_name_a_check(tmp_path: Path) -> None:
    dangling = SUITE + '\n#[ignore = "live seam check: needs nothing"]\n'
    with pytest.raises(MemberError, match="the ignore on line 22 sits above no function"):
        live_seam_checks(suite(tmp_path, dangling))


def test_a_suite_with_no_ignored_check_left_is_a_failure(tmp_path: Path) -> None:
    with pytest.raises(MemberError, match="came back empty"):
        live_seam_checks(suite(tmp_path, "//! Nothing ignored here.\n"))


def test_a_suite_that_is_not_there_is_named(tmp_path: Path) -> None:
    with pytest.raises(MemberError, match="cannot read body/crates/rpc/tests/live"):
        live_seam_checks(tmp_path)


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


GUARD = '"""A miniature with a command line."""\n\n\nif __name__ == "__main__":\n    main()\n'


def split(root: Path, *, runs: tuple[str, ...], read: tuple[str, ...]) -> Path:
    """Write a small `scripts/` where ``runs`` have a main guard and ``read`` do not."""
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
    root = split(tmp_path, runs=("linecap.py",), read=("values.py",))
    assert cli_gate_modules(root) | library_gate_modules(root) == gate_modules(root)
    assert not cli_gate_modules(root) & library_gate_modules(root)


def test_a_guard_that_is_not_at_the_top_level_is_not_a_cli(tmp_path: Path) -> None:
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
    root = split(tmp_path, runs=("linecap.py",), read=())
    with pytest.raises(MemberError, match="came back empty"):
        library_gate_modules(root)


def test_a_module_that_cannot_be_read_is_named_rather_than_sorted(tmp_path: Path) -> None:
    root = split(tmp_path, runs=("linecap.py",), read=("values.py",))
    (root / rostermembers.GATES / "values.py").write_bytes(b"\xff\xfe not text at all")
    with pytest.raises(MemberError, match=r"cannot read scripts/values\.py"):
        library_gate_modules(root)


def test_a_disagreement_between_the_two_files_arrives_as_a_member_failure(tmp_path: Path) -> None:
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
    (tmp_path / scanrecipes.JUSTFILE).write_text("check:\n    echo nothing\n", encoding="utf-8")
    workflow = tmp_path / scanrecipes.WORKFLOW
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text("jobs:\n  cross-tree:\n    steps:\n      - uses: a@b\n", encoding="utf-8")
    with pytest.raises(MemberError, match="came back empty"):
        cross_tree_scans(tmp_path)


def test_the_real_gate_runs_the_scans_this_repo_documents() -> None:
    assert "rostercheck.py" in cross_tree_scans(REPO_ROOT)


def test_a_part_is_read_as_the_tuple_name_its_file_name_gives_it(tmp_path: Path) -> None:
    root = gates(tmp_path, "wirecouplings.py", "logcouplings.py", "couplings.py", "registry.py")
    assert registry_tuples(root) == frozenset({"WIRE_COUPLINGS", "LOG_COUPLINGS"})


def test_the_vocabulary_file_is_not_a_part(tmp_path: Path) -> None:
    root = gates(tmp_path, "wirecouplings.py", "couplings.py")
    assert registry_tuples(root) == frozenset({"WIRE_COUPLINGS"})


def test_a_registry_with_no_part_but_its_vocabulary_is_a_failure(tmp_path: Path) -> None:
    with pytest.raises(MemberError, match="came back empty"):
        registry_tuples(gates(tmp_path, "couplings.py"))


def packages(root: Path, *names: str) -> Path:
    """Write a small `brain/packages/` with exactly ``names`` in it, and return the root."""
    return _workspace(root, rostermembers.PACKAGES, names)


def crates(root: Path, *names: str) -> Path:
    """Write a small `body/crates/` with exactly ``names`` in it, and return the root."""
    return _workspace(root, rostermembers.CRATES, names)


def _workspace(root: Path, tree: Path, names: tuple[str, ...]) -> Path:
    """Write one small workspace with exactly ``names`` as directories."""
    made = root / tree
    made.mkdir(parents=True, exist_ok=True)
    for name in names:
        (made / name).mkdir()
    return root


def test_every_directory_under_the_workspace_is_a_package(tmp_path: Path) -> None:
    root = packages(tmp_path, "core", "seam", "tools")
    assert brain_packages(root) == frozenset({"core", "seam", "tools"})


def test_a_file_beside_the_packages_is_not_one(tmp_path: Path) -> None:
    root = packages(tmp_path, "core")
    (root / rostermembers.PACKAGES / "README.md").write_text("a note\n", encoding="utf-8")
    assert brain_packages(root) == frozenset({"core"})


def test_a_workspace_that_is_not_there_is_named(tmp_path: Path) -> None:
    with pytest.raises(MemberError, match="brain/packages is not a directory"):
        brain_packages(tmp_path)


def test_a_workspace_holding_no_package_is_a_failure(tmp_path: Path) -> None:
    (tmp_path / rostermembers.PACKAGES).mkdir(parents=True)
    with pytest.raises(MemberError, match="came back empty"):
        brain_packages(tmp_path)


def test_every_directory_under_the_body_workspace_is_a_crate(tmp_path: Path) -> None:
    root = crates(tmp_path, "core", "os_windows", "rpc")
    assert body_crates(root) == frozenset({"core", "os_windows", "rpc"})


def test_a_body_workspace_that_is_not_there_is_named(tmp_path: Path) -> None:
    with pytest.raises(MemberError, match="body/crates is not a directory"):
        body_crates(tmp_path)


def test_a_body_workspace_holding_no_crate_is_a_failure(tmp_path: Path) -> None:
    (tmp_path / rostermembers.CRATES).mkdir(parents=True)
    with pytest.raises(MemberError, match="came back empty"):
        body_crates(tmp_path)


def test_the_real_suite_and_the_real_registry_are_both_read() -> None:
    assert len(live_seam_checks(REPO_ROOT)) > 1
    assert len(registry_tuples(REPO_ROOT)) > 1
    assert "rostermembers.py" in gate_modules(REPO_ROOT)
    assert "orchestrator" in brain_packages(REPO_ROOT)
    assert "os_windows" in body_crates(REPO_ROOT)


def test_the_real_tree_really_holds_both_halves() -> None:
    assert "rostercheck.py" in cli_gate_modules(REPO_ROOT)
    assert "rostermembers.py" in library_gate_modules(REPO_ROOT)
    assert cli_gate_modules(REPO_ROOT) | library_gate_modules(REPO_ROOT) == gate_modules(REPO_ROOT)
