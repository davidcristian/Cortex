"""Which files in this tree are compose files, answered once for the gates that ask.

Four gates walk the repo for compose files and must walk to the same answer: `bindcheck.py`
reads the bind mounts they declare, `defaultcheck.py` reads the substitutions they spend,
`volumecheck.py` reads what each service runs against the volume paths its image declares, and
`flagcheck.py` reads which of those services serve subagents and what each is started with. A
second copy of this walk would leave one gate reading a new override file while its siblings did
not, with nothing reported, which is the shape of defect all three exist to remove. So the question
lives here, and no gate writes it twice.

The directory skips are shared for the same reason the names are: a compose file inside a
vendored tree or a build output belongs to something this repo did not write, and that is true
of it whichever gate is asking. They are `skippeddirs.py`'s, the list every walk here reads;
what a gate may add to that list is its own, the line cap's two names being the only addition
in the tree.

Finding nothing is a failure rather than an empty pass, which is the one rule this module
carries of its own: a scan whose glob matched nothing would report success forever.

**Which of those files is the base** is the same question asked one step further, so it is
answered here too. Only the bare-stemmed file is what compose reads when handed no `-f` at all,
and only it pins the project name that an override, layered onto it, runs under. A gate keyed on
the image a container really runs needs that name to key a service that only builds, and it needs
to read the stems to find it, which is what this module already does.
"""

from collections.abc import Iterable
from pathlib import Path

from skippeddirs import SKIPPED_DIRS

# What a compose file is called. Both stems and both suffixes, because a scan that silently
# missed a new override file is the defect the gates reading this exist to prevent.
COMPOSE_STEMS = ("docker-compose", "compose")
COMPOSE_SUFFIXES = frozenset({".yml", ".yaml"})


class ComposeSearchError(Exception):
    """No compose file was found where a gate needs at least one."""


def compose_files(root: Path) -> list[Path]:
    """Return every compose file under ``root``, raising rather than reporting success on none."""
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


def base_project(pinned: Iterable[tuple[Path, str | None]]) -> str | None:
    """The project name an override with none of its own inherits, taken from the base file.

    Compose runs a service that only builds under an image called `<project>-<service>`, so a gate
    keyed on what a container really runs can only key that service once the project is known, and
    an override does not pin one: it is layered onto the base and takes the base's. The base is the
    file compose reads when handed no `-f` at all, which is the one whose stem is bare. Exactly one
    such file must pin a name. None and several are both answers this module does not guess at, and
    the caller then draws a fault of its own rather than keying a silently wrong row.
    """
    named = [
        project for path, project in pinned if project is not None and path.stem in COMPOSE_STEMS
    ]
    return named[0] if len(named) == 1 else None
