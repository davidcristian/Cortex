"""Which files in this tree are compose files, answered once for the gates that ask."""

from pathlib import Path

# Directory components no gate reads. Vendored trees, build output and tool caches.
SKIPPED_DIRS = frozenset(
    {".git", ".venv", ".claude", "target", "node_modules", "__pycache__", "dist", "coverage"}
)

# What a compose file is called. Both stems and both suffixes, because a scan that silently
# missed a new override file is the defect the gates reading this exist to prevent.
COMPOSE_STEMS = ("docker-compose", "compose")
COMPOSE_SUFFIXES = frozenset({".yml", ".yaml"})


class ComposeSearchError(Exception):
    """No compose file was found where a gate needs at least one."""


def compose_files(root: Path) -> list[Path]:
    """Return every compose file under ``root``, refusing to report success on none."""
    found: list[Path] = []
    for directory, dirnames, filenames in root.walk():
        dirnames[:] = sorted(name for name in dirnames if name not in SKIPPED_DIRS)
        found.extend(
            directory / name
            for name in sorted(filenames)
            if Path(name).suffix in COMPOSE_SUFFIXES
            and Path(name).stem.startswith(COMPOSE_STEMS)
            and (directory / name).is_file()
        )
    if not found:
        msg = f"no compose file under {root}; a scan that matched nothing cannot fail"
        raise ComposeSearchError(msg)
    return found
