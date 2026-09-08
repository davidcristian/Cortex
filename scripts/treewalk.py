"""The one directory walk every reader here uses, with the skipped directories applied."""

from collections.abc import Callable, Iterator
from pathlib import Path

from skippeddirs import SKIPPED_DIRS


def any_directory(_inside: Path) -> bool:
    """Enter every directory the shared skip list does not name, which is what most readers need."""
    return True


def walk_files(
    root: Path,
    *,
    also_skip: frozenset[str] = frozenset(),
    enter: Callable[[Path], bool] = any_directory,
) -> Iterator[Path]:
    """Yield every regular file under ``root``, skipped trees never entered."""
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
