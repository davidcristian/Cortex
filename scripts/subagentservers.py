"""Which servers a composed stack starts as subagents, read off the stack's own wiring and argv.

`flagcheck.py` owns the rule and this module owns the set it is applied to, the split
`bindcheck.py` and `composemounts.py` already use, with `composestarts.py` split out again for the
compose syntax underneath. What it answers is the set nothing here could enumerate before: the
subagent servers are not a directory listing and not a name written on a page, so a check over
them had to name each one by hand, and a server added tomorrow was registered by whoever
remembered.

**A service is a subagent server for either of two reasons, and each catches what the other
misses.** The wiring says so: an environment value under `CORTEX_SUBAGENTS_ENDPOINT`,
`CORTEX_SUBAGENTS_GPU_ENDPOINT` or a `CORTEX_SUBAGENTS_ROSTER__<name>` object writes its address
(ADR-0010/0018), and the host inside that address is a service name on the compose network. Or the
argv says so: the command names its model file under a `CORTEX_MODEL_FILE_SUBAGENT*` variable,
which is how both shipped servers spell the pick and how nothing else in the tree spells anything.
The first alone misses a server whose override leaves its address to the host environment; the
second alone misses one whose model path is written out. **The image is not part of the answer**,
and deliberately: `docker-compose.memory.yml` starts the CPU embedder from the very same llama.cpp
image, and a rule that read the image would demand a chat template of a server that serves no chat.

**A service that declares no command of its own is not one.** Its argv comes from somewhere this
reader cannot see, which is either an image's entrypoint or a supervisor: the model host's
subagent tier is a child process it starts by hand, and `hostedtiers.py` reads that placement off
the sidecar's own declaration, so the rule reaches it without this reader guessing at a service
whose command is not written here. Nothing is lost either way, because a llama.cpp server started
with no command names no model and never serves a request, so a subagent server without one is a
stack that fails loudly rather than a tier that answers wrongly.

**An endpoint that writes no address dials nothing here.** A deployment may pass the variable
straight through and name the server only in the host environment, which is a legitimate shape and
not one any reader of this tree can resolve. Such a server is still found by its argv on the day
this tree starts it, which is the day it becomes this gate's business.

**The wiring is read across the whole tree before any service is judged**, because the file that
dials a server and the file that starts it need not be one file: a stack is layered, and the
roster override adds an entry to a wiring the file under it opened.
"""

import re
from pathlib import Path
from typing import NamedTuple

from composedefaults import SubstitutionReadError, read_line
from composefiles import compose_files
from composestarts import ComposeStartError, Started, read_starts

# The environment keys the brain's subagent wiring dials a server through: two flat ones, and one
# JSON object per alternate roster entry, whose own `endpoint` and `gpu_endpoint` are servers too.
ENDPOINT_KEYS = frozenset({"CORTEX_SUBAGENTS_ENDPOINT", "CORTEX_SUBAGENTS_GPU_ENDPOINT"})
ROSTER_PREFIX = "CORTEX_SUBAGENTS_ROSTER__"

# What a subagent server's own argv names its model file under. The shipped pick, the roster
# alternate and the sidecar's opt-in tier are `CORTEX_MODEL_FILE_SUBAGENT` and that name with
# `_QWEN` and `_GPU` after it; the embedder and the cortex name theirs under words this cannot
# reach.
MODEL_PREFIX = "CORTEX_MODEL_FILE_SUBAGENT"

# The host half of an address, which on a compose network is a service name.
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
