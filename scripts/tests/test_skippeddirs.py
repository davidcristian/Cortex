"""Tests for the shared directory skip list.

Two claims are checked here and neither is about a walk. The first is that every walk in this
tree prunes with this list rather than a copy of it, which is how the hand-copied twin that was
already here went unnoticed. The second is the claim the list's own docstring makes about
`.gitignore`, measured against git's answer for this repo rather than taken on trust.
"""

import subprocess
from pathlib import Path

from gitenv import git_env
from skippeddirs import SKIPPED_DIRS

GATES = Path(__file__).resolve().parents[1]
REPO_ROOT = GATES.parent
# How a walk is spelled here: `root.walk()` with its directory list pruned in place.
WALK = "dirnames[:]"
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


def test_every_walk_here_prunes_with_this_list() -> None:
    """Every module under `scripts/` that prunes a walk imports `SKIPPED_DIRS`.

    One of the four already carried a list of its own, a hand-copied twin of the dash ban's that
    nothing compared against. The four are named as a floor: without them a scan that matched no
    files would pass forever.
    """
    sources = {path.name: path.read_text(encoding="utf-8") for path in GATES.glob("*.py")}
    walkers = {name for name, text in sources.items() if WALK in text}
    assert {"backloganchors.py", "composefiles.py", "dashcheck.py", "linecap.py"} <= walkers
    assert [name for name in sorted(walkers) if "skippeddirs import" not in sources[name]] == []


def test_the_overlap_with_gitignore_is_measured_rather_than_believed() -> None:
    """Eight of the ten names are also ignored by git everywhere; `.git` and `coverage` are not.

    A failure here means the overlap moved, not that a gate broke. If a name below started being
    ignored everywhere, the list carries one more restatement and the count in its docstring is
    stale. If one stopped, a walk is now the only thing skipping that tree.
    """
    restatements = {name for name in SKIPPED_DIRS if _ignored_anywhere(name)}
    assert SKIPPED_DIRS - restatements == NOT_RESTATEMENTS
    assert len(restatements) == 8
