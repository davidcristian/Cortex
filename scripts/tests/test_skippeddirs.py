"""What the shared skip list is, and what it deliberately is not.

Two claims are worth a test here and neither is about a walk. The first is that every walk in
this tree prunes with this list rather than a copy of it, which is how the copy that was already
here went unnoticed. The second is the one the list's own docstring makes about `.gitignore`,
measured against git's answer for this repo rather than remembered from the day it was written.
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
# The two names git does not answer for wherever they appear, and the whole reason this list
# cannot become the ignore listing alone.
NOT_RESTATEMENTS = {".git", "coverage"}


def _ignored_anywhere(name: str) -> bool:
    """Whether git ignores a directory of this name wherever it appears in this repo.

    The user's own excludes file is taken out of the question: this asks what the repo's
    `.gitignore` files say, and a global rule on one machine would otherwise change the answer.
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
    """A walk with a list of its own is the defect this module was written to remove.

    One of the four already had one, a hand-copied twin of the dash ban's that nothing compared
    it to. So the obligation is structural rather than remembered, and the four are named as a
    floor, since a scan that matched nothing would report this forever.
    """
    sources = {path.name: path.read_text(encoding="utf-8") for path in GATES.glob("*.py")}
    walkers = {name for name, text in sources.items() if WALK in text}
    assert {"backloganchors.py", "composefiles.py", "dashcheck.py", "linecap.py"} <= walkers
    assert [name for name in sorted(walkers) if "skippeddirs import" not in sources[name]] == []


def test_the_overlap_with_gitignore_is_measured_rather_than_believed() -> None:
    """Eight of the ten names restate a rule git already knows, and two do not.

    A red here is not a bug in a gate: it means the overlap moved. If a name below started being
    ignored everywhere, the list carries one more restatement and the docstring's count is stale.
    If one stopped, a walk is now the only thing skipping that tree, which is the case this list
    exists for and is worth knowing about.
    """
    restatements = {name for name in SKIPPED_DIRS if _ignored_anywhere(name)}
    assert SKIPPED_DIRS - restatements == NOT_RESTATEMENTS
    assert len(restatements) == 8
