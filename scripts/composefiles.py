"""Which files in this tree are compose files, read once for every check that asks."""

from collections.abc import Iterable
from pathlib import Path

from treewalk import walk_files

COMPOSE_STEMS = ("docker-compose", "compose")
COMPOSE_SUFFIXES = frozenset({".yml", ".yaml"})


class ComposeSearchError(Exception):
    """No compose file was found where a check needs at least one."""


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


def base_project(projects: Iterable[tuple[Path, str | None]]) -> str | None:
    """The project name an override with none of its own inherits, taken from the base file."""
    named = [
        project for path, project in projects if project is not None and path.stem in COMPOSE_STEMS
    ]
    return named[0] if len(named) == 1 else None


def refused_summary(gate: str, count: int, unread: str) -> str:
    """The summary a check prints when its reader could not read ``count`` compose files."""
    return (
        f"\n{gate}: {count} compose file(s) could not be read, so {unread}. Rewrite a form the "
        "reader refuses in one it takes, or save the file as UTF-8 text, as the file's own fault "
        "says."
    )
