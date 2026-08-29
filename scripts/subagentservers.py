"""Which servers a composed stack starts as subagents, read off the stack's own wiring and argv."""

import re
from pathlib import Path
from typing import NamedTuple

from composedefaults import SubstitutionReadError, read_line
from composefiles import compose_files
from composestarts import ComposeStartError, Started, read_starts

ENDPOINT_KEYS = frozenset({"CORTEX_SUBAGENTS_ENDPOINT", "CORTEX_SUBAGENTS_GPU_ENDPOINT"})
ROSTER_PREFIX = "CORTEX_SUBAGENTS_ROSTER__"

FAMILY_PREFIX = "CORTEX_MODEL_FILE_"
MODEL_PREFIX = f"{FAMILY_PREFIX}SUBAGENT"

_ADDRESS = re.compile(r"https?://(?P<host>[A-Za-z0-9._-]+)")


class Server(NamedTuple):
    """One subagent server a composed stack starts, and the argv it starts it with."""

    file: str
    service: str
    line: int
    command: tuple[str, ...]


def dialed(started: Started) -> frozenset[str]:
    """Every server one service's environment dials as a subagent, by the address it writes."""
    return frozenset(
        found.group("host")
        for key, value in started.environment
        if key in ENDPOINT_KEYS or key.startswith(ROSTER_PREFIX)
        for found in _ADDRESS.finditer(value)
    )


def names_a_subagent_model(started: Started) -> bool:
    """Whether an argv names its own model file under the subagent variable prefix."""
    command = started.command or ()
    try:
        return any(
            spend.name.startswith(MODEL_PREFIX)
            for item in command
            for spend in read_line(started.line, item)
        )
    except SubstitutionReadError as err:
        msg = f"the command of {started.service!r} cannot be read: {err}"
        raise ComposeStartError(msg) from err


def _read(path: Path) -> str:
    """Read one compose file, naming it when it is absent or is not text."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        msg = f"cannot read {path}: {err}"
        raise ComposeStartError(msg) from err


def servers(root: Path) -> tuple[Server, ...]:
    """Every subagent server the compose tree under ``root`` starts, in the order it is walked."""
    files = [(path, read_starts(_read(path))) for path in compose_files(root)]
    wired = {host for _, starts in files for started in starts for host in dialed(started)}
    return tuple(
        Server(
            file=path.relative_to(root).as_posix(),
            service=started.service,
            line=started.line,
            command=started.command,
        )
        for path, starts in files
        for started in starts
        if started.command is not None
        and (started.service in wired or names_a_subagent_model(started))
    )
