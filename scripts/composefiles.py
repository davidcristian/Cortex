"""Which files in this tree are compose files, answered once for the gates that ask.

Two gates walk the repo for compose files and must walk to the same answer: `bindcheck.py`
reads the bind mounts they declare, `defaultcheck.py` reads the substitutions they spend. A
second copy of this walk is a gate that learns about a new override file while its sibling
does not, in silence, which is the shape of defect both of them exist to remove. So the
question lives here, and neither gate spells it twice.

The directory skips are shared for the same reason the names are: a compose file inside a
vendored tree or a build output belongs to something this repo did not write, and that is true
of it whichever gate is asking. This deliberately does not join the per-gate `SKIPPED_DIRS`
lists in `linecap.py` and `dashcheck.py`, which differ from each other because each answers to
its own rule (prose in a test is still prose; a 400-line test is not the cap's problem).

Finding nothing is a failure rather than an empty pass, which is the one rule this module
carries of its own: a scan whose glob matched nothing would report success forever.
"""

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
