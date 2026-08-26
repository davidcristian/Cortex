"""Behaviour of the reader that says which scans the single gate actually runs.

The fixtures are miniatures of the two real files: one justfile whose `check` recipe opens with a
run of scans and then forks the trees, one workflow whose `cross-tree` job runs the same list with
sibling jobs written under the same key. Every case below is an edit somebody could really make to
one of those two files, since a scan is added by editing both and the whole point of this reader
is that it refuses to answer while only one of them has been.
"""

from pathlib import Path

import pytest

import scanrecipes
from scanrecipes import (
    ScanReadError,
    gate_scans,
    job_scans,
    recipe_body,
    recipe_module,
    scan_modules,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

JUSTFILE = """\
# `just check` is THE gate.
check:
    #!/usr/bin/env bash
    set -euo pipefail
    just check-linecap
    just check-backlog
    tmp=$(mktemp -d)
    just check-brain >"$tmp/brain.log" 2>&1 &
    wait

# The cross-tree line cap.
check-linecap:
    cd scripts && uv sync --locked
    cd scripts && uv run python linecap.py --root ..

# The backlog index, whose recipe and module are not the same word.
check-backlog:
    cd scripts && uv run python backlogcheck.py --root ..

shuffle seed="":
    cd scripts && uv run pytest
"""

WORKFLOW = """\
jobs:
  changes:
    runs-on: ubuntu-latest
    steps:
      - run: just check-linecap

  # The cross-tree scans are repo-wide.
  cross-tree:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@abc # v7.0.1
      - run: just check-linecap
      - run: just check-backlog

  python:
    runs-on: ubuntu-latest
    steps:
      - run: just check-brain
"""


def files(root: Path, *, justfile: str = JUSTFILE, workflow: str = WORKFLOW) -> Path:
    """Write a miniature repo carrying the two files that run the scans."""
    (root / scanrecipes.JUSTFILE).write_text(justfile, encoding="utf-8")
    workflows = root / scanrecipes.WORKFLOW
    workflows.parent.mkdir(parents=True, exist_ok=True)
    workflows.write_text(workflow, encoding="utf-8")
    return root


# ── what the gate runs, read out of its own recipe ─────────────────────────────


def test_the_run_a_gate_opens_with_is_what_it_runs_first() -> None:
    """The shebang and the shell settings above the run are stepped over, not stopped at."""
    assert gate_scans(JUSTFILE) == ["check-linecap", "check-backlog"]


def test_the_run_stops_at_the_first_command_that_is_not_a_scan() -> None:
    """The trees below it are outside however they are launched, redirection or none.

    Without the stop, a `just check-brain` written plainly would read as an eleventh scan, and
    the reader would be describing the whole gate rather than the run it opens with.
    """
    plainly = JUSTFILE.replace('just check-brain >"$tmp/brain.log" 2>&1 &', "just check-brain")
    assert gate_scans(plainly) == ["check-linecap", "check-backlog"]


def test_a_gate_that_is_nothing_but_its_scans_is_read_to_the_end() -> None:
    """A recipe with no trees to fork has nothing to stop at, and the run is the whole body."""
    only = "check:\n    just check-linecap\n    just check-backlog\n"
    assert gate_scans(only) == ["check-linecap", "check-backlog"]


def test_a_recipe_carrying_parameters_is_still_found() -> None:
    """`shuffle seed="":` is a header like any other, so a scan taking an argument would be too."""
    assert recipe_body(JUSTFILE, "shuffle") == ["    cd scripts && uv run pytest"]


def test_a_recipe_the_justfile_does_not_carry_is_named() -> None:
    with pytest.raises(ScanReadError, match="the 'check-nothing' recipe is not there"):
        recipe_body(JUSTFILE, "check-nothing")


# ── what CI runs, read out of the one job that is the scans ────────────────────


def test_the_job_names_every_recipe_it_runs_and_nothing_a_sibling_runs() -> None:
    """The surprise this reader was rewritten for: every job is written under one key.

    A block that ended only at column zero would swallow the sibling jobs below `cross-tree`,
    and the reader would report the whole workflow as the cross-tree scans.
    """
    assert job_scans(WORKFLOW) == ["check-linecap", "check-backlog"]


def test_a_step_that_is_not_a_check_recipe_is_refused_rather_than_stepped_over() -> None:
    """This job is the scans and nothing else, so a step it was not taught is a fault."""
    widened = WORKFLOW.replace(
        "      - run: just check-backlog",
        "      - run: echo scanning\n      - run: just check-backlog",
    )
    with pytest.raises(ScanReadError, match="runs 'echo scanning', which is not one of"):
        job_scans(widened)


def test_a_workflow_that_lost_the_job_is_named() -> None:
    renamed = WORKFLOW.replace("  cross-tree:", "  scans:")
    with pytest.raises(ScanReadError, match="the 'cross-tree' job is not there"):
        job_scans(renamed)


# ── the module behind a recipe, which is not the recipe's own name ─────────────


def test_a_recipe_answers_with_the_module_it_runs_and_not_with_its_name() -> None:
    assert recipe_module(JUSTFILE, "check-backlog") == "backlogcheck.py"


def test_a_recipe_that_runs_no_module_is_refused() -> None:
    """A recipe running a shell script rather than a module is not a scan this reader can name."""
    with pytest.raises(ScanReadError, match="runs 0 module"):
        recipe_module(JUSTFILE, "shuffle")


def test_a_recipe_that_runs_two_modules_is_refused() -> None:
    """Guessing which of two is the scan would put a claim behind a coin toss."""
    doubled = JUSTFILE.replace(
        "    cd scripts && uv run python backlogcheck.py --root ..",
        "    cd scripts && uv run python backlogcheck.py --root ..\n"
        "    cd scripts && uv run python backlog.py --root ..",
    )
    with pytest.raises(ScanReadError, match=r"runs 2 module\(s\)"):
        recipe_module(doubled, "check-backlog")


# ── the two files together, which is the only answer this reader gives ────────


def test_the_scans_are_what_both_files_run(tmp_path: Path) -> None:
    assert scan_modules(files(tmp_path)) == frozenset({"linecap.py", "backlogcheck.py"})


def test_a_scan_added_to_the_gate_and_not_to_ci_is_refused(tmp_path: Path) -> None:
    """The drift this reader exists to be honest about, arriving from the gate's side."""
    grown = JUSTFILE.replace(
        "    just check-backlog", "    just check-backlog\n    just check-dashcheck"
    )
    with pytest.raises(ScanReadError, match="neither list is the answer while they disagree"):
        scan_modules(files(tmp_path, justfile=grown))


def test_a_scan_added_to_ci_and_not_to_the_gate_is_refused(tmp_path: Path) -> None:
    """And from the other side, since a document agreeing with either half agrees with nothing."""
    grown = WORKFLOW.replace(
        "      - run: just check-backlog",
        "      - run: just check-backlog\n      - run: just check-dashcheck",
    )
    with pytest.raises(ScanReadError, match="neither list is the answer while they disagree"):
        scan_modules(files(tmp_path, workflow=grown))


def test_the_two_files_may_run_the_scans_in_different_orders(tmp_path: Path) -> None:
    """The order a scan runs in is each file's own business, these scans being independent."""
    reordered = WORKFLOW.replace(
        "      - run: just check-linecap\n      - run: just check-backlog",
        "      - run: just check-backlog\n      - run: just check-linecap",
    )
    assert scan_modules(files(tmp_path, workflow=reordered)) == frozenset(
        {"linecap.py", "backlogcheck.py"}
    )


def test_a_file_that_is_not_there_is_named(tmp_path: Path) -> None:
    with pytest.raises(ScanReadError, match="cannot read justfile"):
        scan_modules(tmp_path)


def test_a_workflow_that_cannot_be_decoded_is_named(tmp_path: Path) -> None:
    root = files(tmp_path)
    (root / scanrecipes.WORKFLOW).write_bytes(b"\xff\xfe not text at all")
    with pytest.raises(ScanReadError, match=r"cannot read \.github/workflows/ci\.yml"):
        scan_modules(root)


# ── against the two files this reader is written for ───────────────────────────


def test_the_real_gate_and_the_real_workflow_agree() -> None:
    """The reader over the committed tree, which is also the floor under every roster using it."""
    found = scan_modules(REPO_ROOT)
    assert "rostercheck.py" in found
    assert "backlogcheck.py" in found
    assert len(found) > 1


def test_the_real_gate_runs_a_recipe_whose_module_has_another_name() -> None:
    """The reason a recipe is resolved through its body rather than by trimming its prefix."""
    justfile = (REPO_ROOT / scanrecipes.JUSTFILE).read_text(encoding="utf-8")
    named = {recipe: recipe_module(justfile, recipe) for recipe in gate_scans(justfile)}
    assert any(module != f"{recipe.removeprefix('check-')}.py" for recipe, module in named.items())
