"""Tests for the shared directory skip list."""

import subprocess
from pathlib import Path

from gitenv import git_env
from skippeddirs import SKIPPED_DIRS

GATES = Path(__file__).resolve().parents[1]
REPO_ROOT = GATES.parent
# A directory git tracks, under which nothing named below exists, so what comes back is the
# ignore rules and not a fact about this checkout.
PROBE = "brain/packages/core"
# The two names git does not ignore everywhere they appear, which is why this list cannot be
# replaced by the repo's ignore rules.
NOT_RESTATEMENTS = {".git", "coverage"}


def _ignored_anywhere(name: str) -> bool:
    """Whether git ignores a directory of this name wherever it appears in this repo.

    The user's own excludes file is disabled, so the answer comes from the repo's `.gitignore`
    files alone and a global rule on one machine cannot change it.
    """
    result = subprocess.run(  # noqa: S603 -- fixed argv, no shell
        [  # noqa: S607 -- git on PATH
            "git",
            "-C",
            str(REPO_ROOT),
            "-c",
            "core.excludesFile=/dev/null",
            "check-ignore",
            "-q",
            "--",
            f"{PROBE}/{name}/",
        ],
        capture_output=True,
        check=False,
        env=git_env(),
    )
    assert result.returncode in (0, 1), result.stderr.decode(errors="replace")
    return result.returncode == 0


def test_the_overlap_with_gitignore_is_measured_rather_than_believed() -> None:
    """Eight of the ten names are also ignored by git everywhere; `.git` and `coverage` are not."""
    restatements = {name for name in SKIPPED_DIRS if _ignored_anywhere(name)}
    assert SKIPPED_DIRS - restatements == NOT_RESTATEMENTS
    assert len(restatements) == 8
