"""Every recursive read of a directory tree here, in the one place the skips are applied.

Seven readers under `scripts/` descend a tree and none of them descends it itself: `dashcheck.py`
over every text file, `linecap.py` over three toolchains' source, `backloganchors.py` over the
repo's markdown, `composefiles.py` over the compose files, `logcalls.py` over the brain's modules,
`assertedlines.py` over one suite, and `samplecheck.py` over the runbooks. They ask different
questions and none of the answers is about a dependency's tree, a build output or a tool's cache,
so the descent is written once here and each reader keeps only the question it asks of the files
it is handed.

**This is what `skippeddirs.py` used to be an obligation to remember.** That module holds the
names and the argument for them, and every walk was held to importing it by a test that searched
each file for the pruning line `dirnames[:]`. Three readers written afterwards spelled a filtered
`rglob` instead, so the search recognized none of them and the obligation reached none of them
either. A reader that is handed its files cannot forget a list it never spells, and one that
descends a tree of its own is no longer a walk this tree happens not to have noticed: it is the
only such call outside this module, which is what the suite beside it holds.

**Two per-reader differences stay with their readers**, because neither is about which trees are
worth entering. The line cap skips two more names than everything else, `tests` and `_generated`,
which it passes as `also_skip`. The dash ban prunes what git ignores as well, which it passes as
`enter`, and that predicate is its own: only its rule is about the text this repo owns, so only it
refuses a root git cannot answer about.

Order is the walk's: directories before what they contain, and each directory's entries in name
order. A reader wanting a single sorted run over the whole tree sorts what it is handed, which is
what the three that arrived as globs do.
"""

from collections.abc import Callable, Iterator
from pathlib import Path

from skippeddirs import SKIPPED_DIRS


def any_directory(_inside: Path) -> bool:
    """Enter every directory the shared list does not name, which is what most readers want.

    The path it is handed is what a caller with a rule of its own reads; this one has none.
    """
    return True


def walk_files(
    root: Path,
    *,
    also_skip: frozenset[str] = frozenset(),
    enter: Callable[[Path], bool] = any_directory,
) -> Iterator[Path]:
    """Yield every regular file under ``root``, skipped trees never entered.

    ``also_skip`` names directory components to skip beyond the shared list, and ``enter`` is
    asked about each remaining directory by its path relative to ``root``. A candidate that is not
    a regular file after following symlinks, a dangling editor lockfile being the one this tree
    meets, is not yielded: every reader here goes on to open what it is given.
    """
    skipped = SKIPPED_DIRS | also_skip
    for directory, dirnames, filenames in root.walk():
        inside = directory.relative_to(root)
        dirnames[:] = sorted(
            name for name in dirnames if name not in skipped and enter(inside / name)
        )
        for name in sorted(filenames):
            path = directory / name
            if path.is_file():
                yield path
