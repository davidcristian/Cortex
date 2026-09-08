"""Which files in this tree are compose files, answered once for the gates that ask."""

from collections.abc import Iterable
from pathlib import Path

from treewalk import walk_files

# What a compose file is called. Both stems and both suffixes, because a scan that silently
# missed a new override file is the defect the gates reading this exist to prevent.
COMPOSE_STEMS = ("docker-compose", "compose")
COMPOSE_SUFFIXES = frozenset({".yml", ".yaml"})


class ComposeSearchError(Exception):
    """No compose file was found where a gate needs at least one."""


def compose_files(root: Path) -> list[Path]:
    """Return every compose file under ``root``, raising rather than reporting success on none."""
    found = [
        path
        for path in walk_files(root)
        if path.suffix in COMPOSE_SUFFIXES and path.stem.startswith(COMPOSE_STEMS)
    ]
    if not found:
        msg = f"no compose file under {root}; a scan that matched nothing cannot fail"
        raise ComposeSearchError(msg)
    return found


def base_project(pinned: Iterable[tuple[Path, str | None]]) -> str | None:
    """The project name an override with none of its own inherits, taken from the base file."""
    named = [
        project for path, project in pinned if project is not None and path.stem in COMPOSE_STEMS
    ]
    return named[0] if len(named) == 1 else None
